"""Phase 4 causal graph builder and service tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.graph.builder import CausalGraphBuilder
from app.models.event import Event
from app.models.finding import HypothesisFinding
from app.services.graph_service import GraphService


def _finding(
    *,
    domain: str,
    agent_id: str,
    supporting: list[str] | None = None,
) -> HypothesisFinding:
    fid = uuid.uuid4()
    return HypothesisFinding(
        finding_id=fid,
        case_id=uuid.uuid4(),
        agent_id=agent_id,
        domain=domain,
        hypothesis=f"{domain} may have contributed",
        reasoning="test",
        supporting_evidence=supporting or [],
        contradicting_evidence=[],
        relevant_events=[],
        missing_evidence=[],
        assumptions=[],
        reasoning_summary="test",
        confidence=0.5,
        rank_score=0.4,
    )


def test_builder_creates_outcome_and_evidenced_edges():
    case_id = uuid.uuid4()
    event_id = uuid.uuid4()
    events = [
        Event(
            event_id=event_id,
            case_id=case_id,
            evidence_id=uuid.uuid4(),
            event_type="SPEED_SAMPLE",
            raw_timestamp=datetime.now(timezone.utc),
            corrected_timestamp=datetime.now(timezone.utc),
            timeline_index=0,
        )
    ]
    findings = [
        _finding(
            domain="environment",
            agent_id="environment",
            supporting=["external_weather:open-meteo:2024-08-14T05:00"],
        )
    ]

    builder = CausalGraphBuilder()
    nodes, edges = builder.build(case_id=case_id, events=events, findings=findings)

    node_types = {n.node_type for n in nodes}
    assert "OUTCOME" in node_types
    assert "EVENT" in node_types
    assert "HYPOTHESIS" in node_types
    assert "FACTOR" in node_types

    contributes = [e for e in edges if e.edge_type == "CONTRIBUTES_TO"]
    assert contributes
    assert contributes[0].properties.get("evidence_refs")

    causal = builder.causal_support(findings[0].finding_id, nodes, edges)
    assert causal >= 0.35


def test_builder_skips_edges_without_supporting_evidence():
    case_id = uuid.uuid4()
    findings = [_finding(domain="track", agent_id="track", supporting=[])]

    builder = CausalGraphBuilder()
    nodes, edges = builder.build(case_id=case_id, events=[], findings=findings)
    assert not any(e.edge_type == "CONTRIBUTES_TO" for e in edges)


def test_graph_service_in_memory_build(db_session):
    from app.models.case import Case

    case = Case(case_id=uuid.uuid4(), title="Graph test case", metadata_={})
    db_session.add(case)
    db_session.commit()

    service = GraphService(db_session)
    finding = HypothesisFinding(
        finding_id=uuid.uuid4(),
        case_id=case.case_id,
        agent_id="signalling",
        domain="signalling",
        hypothesis="Signal anomaly",
        reasoning="r",
        supporting_evidence=["evidence_record:abc"],
        contradicting_evidence=[],
        relevant_events=[],
        missing_evidence=[],
        assumptions=[],
        reasoning_summary="s",
        confidence=0.6,
        rank_score=0.5,
    )
    db_session.add(finding)
    db_session.commit()

    graph = service.build_and_persist(case.case_id)
    assert graph is not None
    assert graph.node_count >= 2
    assert graph.edge_count >= 1

    loaded = service.get_graph(case.case_id)
    assert loaded is not None
    assert loaded.node_count == graph.node_count
