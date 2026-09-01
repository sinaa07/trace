"""Orchestrate causal graph build, query, and causal-support rescoring."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.graph.builder import CausalGraphBuilder, GraphEdge, GraphNode
from app.core.graph.store import Neo4jGraphStore
from app.core.investigation.ranking import score_hypothesis
from app.models.finding import HypothesisFinding
from app.schemas.graph import (
    AuditEventResponse,
    AuditListResponse,
    CaseGraphResponse,
    EvidenceGapsResponse,
    GraphEdgeModel,
    GraphNodeModel,
    GraphPathResponse,
)
from app.schemas.investigation import HypothesisFindingCreate, RankingDimensionScores
from app.services.storage.repositories.case_repo import CaseRepository
from app.services.storage.repositories.event_repo import EventRepository
from app.services.storage.repositories.finding_repo import FindingRepository


class GraphService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.cases = CaseRepository(db)
        self.events = EventRepository(db)
        self.findings = FindingRepository(db)
        self.builder = CausalGraphBuilder()
        self._memory: dict[str, tuple[list[GraphNode], list[GraphEdge]]] = {}

    def build_and_persist(self, case_id: uuid.UUID) -> CaseGraphResponse | None:
        if self.cases.get(case_id) is None:
            return None

        events = self.events.list_for_case(case_id)
        findings = self.findings.list_for_case(case_id)
        nodes, edges = self.builder.build(
            case_id=case_id, events=events, findings=findings
        )

        from app.core.config import settings

        if settings.neo4j_enabled:
            store = Neo4jGraphStore()
            try:
                store.replace_case_graph(case_id, nodes, edges)
            finally:
                store.close()
        else:
            self._memory[str(case_id)] = (nodes, edges)

        return self._to_response(case_id, nodes, edges, built_from="investigation")

    def get_graph(self, case_id: uuid.UUID) -> CaseGraphResponse | None:
        if self.cases.get(case_id) is None:
            return None

        from app.core.config import settings

        if settings.neo4j_enabled:
            store = Neo4jGraphStore()
            try:
                raw = store.get_case_graph(case_id)
            finally:
                store.close()
            nodes = [
                GraphNode(
                    id=n["id"],
                    label=n.get("label", n["id"]),
                    node_type=n.get("node_type", "UNKNOWN"),
                    properties={
                        k: v
                        for k, v in n.items()
                        if k not in {"id", "label", "node_type"}
                    },
                )
                for n in raw["nodes"]
            ]
            edges = [
                GraphEdge(
                    source=e["source"],
                    target=e["target"],
                    edge_type=e["edge_type"],
                    properties=e.get("properties") or {},
                )
                for e in raw["edges"]
            ]
        else:
            nodes, edges = self._memory.get(str(case_id), ([], []))

        return self._to_response(case_id, nodes, edges)

    def find_path(
        self, case_id: uuid.UUID, *, from_id: str, to_id: str
    ) -> GraphPathResponse | None:
        if self.cases.get(case_id) is None:
            return None

        from app.core.config import settings

        if settings.neo4j_enabled:
            store = Neo4jGraphStore()
            try:
                result = store.find_path(case_id, from_id=from_id, to_id=to_id)
            finally:
                store.close()
            return GraphPathResponse(
                case_id=case_id,
                from_id=from_id,
                to_id=to_id,
                found=bool(result.get("found")),
                nodes=result.get("nodes") or [],
                edges=result.get("edges") or [],
            )

        nodes, edges = self._memory.get(str(case_id), ([], []))
        # Simple BFS for in-memory fallback
        path = self._bfs_path(from_id, to_id, edges)
        return GraphPathResponse(
            case_id=case_id,
            from_id=from_id,
            to_id=to_id,
            found=path is not None,
            nodes=[n for n in nodes if n.id in (path or [])] if path else [],
            edges=[
                {
                    "source": e.source,
                    "target": e.target,
                    "edge_type": e.edge_type,
                    "properties": e.properties,
                }
                for e in edges
                if path and any(e.source == a and e.target == b for a, b in zip(path, path[1:]))
            ],
        )

    def rescore_findings_with_causal_support(
        self, case_id: uuid.UUID
    ) -> list[HypothesisFinding]:
        findings = self.findings.list_for_case(case_id)
        if not findings:
            return []

        graph = self.get_graph(case_id)
        if graph is None:
            return findings

        nodes = [
            GraphNode(
                id=n.id,
                label=n.label,
                node_type=n.node_type,
                properties=n.properties,
            )
            for n in graph.nodes
        ]
        edges = [
            GraphEdge(
                source=e.source,
                target=e.target,
                edge_type=e.edge_type,
                properties=e.properties,
            )
            for e in graph.edges
        ]

        updated: list[HypothesisFinding] = []
        for row in findings:
            causal = self.builder.causal_support(row.finding_id, nodes, edges)
            finding_create = HypothesisFindingCreate(
                domain=row.domain,
                hypothesis=row.hypothesis,
                reasoning=row.reasoning,
                supporting_evidence=list(row.supporting_evidence or []),
                contradicting_evidence=list(row.contradicting_evidence or []),
                relevant_events=[str(x) for x in (row.relevant_events or [])],
                missing_evidence=list(row.missing_evidence or []),
                assumptions=list(row.assumptions or []),
                reasoning_summary=row.reasoning_summary or "",
                confidence=row.confidence,
                uncertainty=row.uncertainty,
                domain_features=row.domain_features,
            )
            dims_data = row.rank_dimensions if isinstance(row.rank_dimensions, dict) else {}
            dims, weighted = score_hypothesis(
                finding_create,
                source_reliability=float(dims_data.get("source_reliability", 0.7)),
                temporal_consistency=float(dims_data.get("temporal_consistency", 0.7)),
                causal_support=causal,
            )
            row.rank_score = weighted
            row.rank_dimensions = dims.model_dump()
            updated.append(row)
        self.db.flush()
        return updated

    def get_evidence_gaps(self, case_id: uuid.UUID) -> EvidenceGapsResponse | None:
        if self.cases.get(case_id) is None:
            return None
        from app.core.mcp.tools import EvidenceTools

        gaps = EvidenceTools(self.db, case_id).get_evidence_gaps()
        case = self.cases.get(case_id)
        has_coords = bool(
            case
            and case.location
            and (
                case.location.get("lat")
                or case.location.get("latitude")
                or case.location.get("lon")
                or case.location.get("longitude")
            )
        )
        return EvidenceGapsResponse(
            case_id=case_id,
            missing_source_types=gaps.get("missing_source_types") or [],
            missing_domain_inputs=gaps.get("missing_domain_inputs") or [],
            needs_review_or_failed=gaps.get("needs_review_or_failed") or [],
            external_weather_available=has_coords,
        )

    def list_audit(self, case_id: uuid.UUID) -> AuditListResponse | None:
        if self.cases.get(case_id) is None:
            return None
        from app.models import AuditEvent
        from sqlalchemy import select

        rows = list(
            self.db.scalars(
                select(AuditEvent)
                .where(AuditEvent.case_id == case_id)
                .order_by(AuditEvent.created_at.desc())
            ).all()
        )
        events = [
            AuditEventResponse(
                audit_id=r.audit_id,
                case_id=r.case_id,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                action=r.action,
                actor=r.actor,
                payload=r.payload,
                created_at=r.created_at.isoformat(),
            )
            for r in rows
        ]
        return AuditListResponse(case_id=case_id, events=events, total=len(events))

    @staticmethod
    def _to_response(
        case_id: uuid.UUID,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        *,
        built_from: str | None = None,
    ) -> CaseGraphResponse:
        return CaseGraphResponse(
            case_id=case_id,
            nodes=[
                GraphNodeModel(
                    id=n.id,
                    label=n.label,
                    node_type=n.node_type,
                    properties=n.properties,
                )
                for n in nodes
            ],
            edges=[
                GraphEdgeModel(
                    source=e.source,
                    target=e.target,
                    edge_type=e.edge_type,
                    properties=e.properties,
                )
                for e in edges
            ],
            node_count=len(nodes),
            edge_count=len(edges),
            built_from=built_from,
        )

    @staticmethod
    def _bfs_path(from_id: str, to_id: str, edges: list[GraphEdge]) -> list[str] | None:
        adj: dict[str, list[str]] = {}
        for e in edges:
            adj.setdefault(e.source, []).append(e.target)
        queue = [(from_id, [from_id])]
        seen = {from_id}
        while queue:
            node, path = queue.pop(0)
            if node == to_id:
                return path
            for nxt in adj.get(node, []):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, path + [nxt]))
        return None
