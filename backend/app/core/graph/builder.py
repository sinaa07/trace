"""Build evidence-linked causal graph structures from case events + findings."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.models.event import Event
from app.models.finding import HypothesisFinding

TEMPLATES_PATH = Path(__file__).with_name("templates.yaml")


@dataclass
class GraphNode:
    id: str
    label: str
    node_type: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    edge_type: str
    properties: dict[str, Any] = field(default_factory=dict)


class CausalGraphBuilder:
    """Materialize blueprint node/edge types from investigation artifacts."""

    def __init__(self, templates_path: Path | None = None) -> None:
        self.templates_path = templates_path or TEMPLATES_PATH
        self._templates = self._load_templates()

    def build(
        self,
        *,
        case_id: uuid.UUID,
        events: list[Event],
        findings: list[HypothesisFinding],
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []

        outcome = self._templates.get("outcome") or {}
        outcome_id = f"outcome:{outcome.get('id', 'incident_outcome')}"
        nodes[outcome_id] = GraphNode(
            id=outcome_id,
            label=str(outcome.get("label", "Incident outcome")),
            node_type="OUTCOME",
            properties={"case_id": str(case_id), "template_id": outcome.get("id")},
        )

        sorted_events = sorted(
            events,
            key=lambda e: (
                e.timeline_index if e.timeline_index is not None else 10**9,
                e.corrected_timestamp or e.raw_timestamp,
            ),
        )
        prev_event_id: str | None = None
        for event in sorted_events:
            node_id = f"event:{event.event_id}"
            nodes[node_id] = GraphNode(
                id=node_id,
                label=event.event_type,
                node_type="EVENT",
                properties={
                    "case_id": str(case_id),
                    "event_id": str(event.event_id),
                    "event_type": event.event_type,
                    "entity_id": event.entity_id,
                    "corrected_timestamp": (
                        event.corrected_timestamp.isoformat()
                        if event.corrected_timestamp
                        else None
                    ),
                    "timeline_index": event.timeline_index,
                },
            )
            if prev_event_id:
                edges.append(
                    GraphEdge(
                        source=prev_event_id,
                        target=node_id,
                        edge_type="PRECEDES",
                        properties={"case_id": str(case_id)},
                    )
                )
            prev_event_id = node_id

        domain_templates: dict[str, Any] = self._templates.get("domains") or {}
        for finding in findings:
            if finding.agent_id == "meta":
                continue

            hyp_id = f"hypothesis:{finding.finding_id}"
            nodes[hyp_id] = GraphNode(
                id=hyp_id,
                label=finding.hypothesis[:120],
                node_type="HYPOTHESIS",
                properties={
                    "case_id": str(case_id),
                    "finding_id": str(finding.finding_id),
                    "agent_id": finding.agent_id,
                    "domain": finding.domain,
                    "confidence": finding.confidence,
                    "rank_score": finding.rank_score,
                },
            )

            template = domain_templates.get(finding.domain) or domain_templates.get(
                finding.agent_id
            )
            if not template:
                continue

            factor_id = f"factor:{template['factor_id']}"
            if factor_id not in nodes:
                nodes[factor_id] = GraphNode(
                    id=factor_id,
                    label=str(template["factor_label"]),
                    node_type=str(template.get("node_type", "FACTOR")),
                    properties={
                        "case_id": str(case_id),
                        "domain": finding.domain,
                        "template_factor_id": template["factor_id"],
                    },
                )

            supporting = list(finding.supporting_evidence or [])
            if not supporting:
                continue

            edges.append(
                GraphEdge(
                    source=hyp_id,
                    target=factor_id,
                    edge_type="ASSERTS",
                    properties={
                        "case_id": str(case_id),
                        "evidence_refs": supporting,
                        "confidence": finding.confidence,
                    },
                )
            )

            for rel in template.get("edges") or []:
                target_key = rel.get("to", "incident_outcome")
                target_id = (
                    outcome_id
                    if target_key == "incident_outcome"
                    else f"factor:{target_key}"
                )
                edges.append(
                    GraphEdge(
                        source=factor_id,
                        target=target_id,
                        edge_type=str(rel.get("type", "CONTRIBUTES_TO")),
                        properties={
                            "case_id": str(case_id),
                            "finding_id": str(finding.finding_id),
                            "evidence_refs": supporting,
                            "strength": finding.rank_score or finding.confidence,
                        },
                    )
                )

            for event_ref in finding.relevant_events or []:
                event_node = f"event:{event_ref}"
                if event_node in nodes:
                    edges.append(
                        GraphEdge(
                            source=event_node,
                            target=hyp_id,
                            edge_type="CITED_BY",
                            properties={
                                "case_id": str(case_id),
                                "event_id": str(event_ref),
                            },
                        )
                    )

        return list(nodes.values()), edges

    def causal_support(
        self,
        finding_id: uuid.UUID,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> float:
        """Score paths from hypothesis → factor → outcome with evidence refs."""
        hyp_id = f"hypothesis:{finding_id}"
        if not any(n.id == hyp_id for n in nodes):
            return 0.0

        adjacency: dict[str, list[GraphEdge]] = {}
        for edge in edges:
            adjacency.setdefault(edge.source, []).append(edge)

        def has_evidence(edge: GraphEdge) -> bool:
            refs = edge.properties.get("evidence_refs") or []
            return bool(refs)

        # BFS for paths hyp → ... → outcome with at least one evidenced edge
        best = 0.0
        stack: list[tuple[str, float, bool]] = [(hyp_id, 0.0, False)]
        visited: set[tuple[str, bool]] = set()

        while stack:
            node_id, depth, saw_evidence = stack.pop()
            key = (node_id, saw_evidence)
            if key in visited:
                continue
            visited.add(key)

            node = next((n for n in nodes if n.id == node_id), None)
            if node and node.node_type == "OUTCOME" and saw_evidence:
                # Shorter evidenced paths score higher
                best = max(best, max(0.35, 1.0 - depth * 0.15))
                continue

            if depth >= 6:
                continue

            for edge in adjacency.get(node_id, []):
                next_evidence = saw_evidence or has_evidence(edge)
                if edge.edge_type in {
                    "ASSERTS",
                    "CONTRIBUTES_TO",
                    "CAUSES",
                    "ENABLES",
                    "PRECEDES",
                    "CITED_BY",
                }:
                    stack.append((edge.target, depth + 1, next_evidence))

        return round(min(best, 1.0), 4)

    @staticmethod
    def _load_templates() -> dict[str, Any]:
        with TEMPLATES_PATH.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
