"""Phase 3 investigation agents: MCP tools, heuristic orchestrator, APIs."""

from __future__ import annotations

from pathlib import Path

from app.core.agents.synthesizer import synthesize_finding
from app.core.mcp.tools import EvidenceTools, TOOL_NAMES


def _create_case_with_signal(client, test_data_dir: Path) -> str:
    resp = client.post(
        "/cases",
        json={
            "title": "Investigation fixture case",
            "incident_time": "2024-06-01T04:30:00Z",
            "created_by": "tester",
            "metadata": {
                "duty": {"duty_hours": 10.0},
                "weather": {"visibility_m": 120.0, "wind_speed_kmh": 85.0},
            },
        },
    )
    assert resp.status_code == 201
    case_id = resp.json()["case_id"]

    signal = test_data_dir / "signal_log.csv"
    with signal.open("rb") as fh:
        up = client.post(
            f"/cases/{case_id}/evidence",
            data={"source_type": "signal_log", "actor": "tester"},
            files={"file": ("signal_log.csv", fh, "text/csv")},
        )
    assert up.status_code == 201
    return case_id


def test_mcp_tool_names_match_blueprint():
    for name in (
        "query_evidence",
        "get_event",
        "get_events",
        "get_timeline",
        "get_source_metadata",
        "get_evidence_provenance",
        "get_evidence_gaps",
    ):
        assert name in TOOL_NAMES


def test_heuristic_synthesizer_produces_finding():
    finding = synthesize_finding(
        agent_id="signalling",
        tool_results={
            "get_domain_features": {
                "domains": [
                    {
                        "domain": "signalling",
                        "score": 0.6,
                        "summary": "2 signal anomalies",
                        "missing_inputs": [],
                        "features": {},
                    }
                ]
            },
            "query_evidence": {
                "items": [
                    {
                        "record_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                        "source_type": "signal_log",
                    }
                ]
            },
            "get_events": {"items": []},
            "get_anomalies": {
                "items": [
                    {
                        "anomaly_id": "11111111-2222-3333-4444-555555555555",
                        "rule_id": "invalid_signal_transition",
                        "title": "Bad transition",
                        "affected_event_ids": [],
                    }
                ]
            },
            "get_conflicts": {"items": []},
            "get_evidence_gaps": {"missing_source_types": ["weather"], "missing_domain_inputs": []},
        },
    )
    assert finding.domain == "signalling"
    assert finding.hypothesis
    assert finding.confidence > 0
    assert any("anomaly:" in s for s in finding.supporting_evidence)


def test_environment_synthesizer_merges_external_weather():
    finding = synthesize_finding(
        agent_id="environment",
        tool_results={
            "get_domain_features": {
                "domains": [
                    {
                        "domain": "weather",
                        "score": None,
                        "summary": "No weather measurements available for threshold scoring.",
                        "missing_inputs": [
                            "visibility_m",
                            "wind_speed_kmh",
                            "rainfall_mm_hour",
                            "rail_temp_c",
                            "ambient_temp_c",
                        ],
                        "features": {},
                    }
                ]
            },
            "fetch_weather_at_location": {
                "coordinates": {
                    "latitude": 26.5655,
                    "longitude": 80.515,
                    "source": "case.location",
                },
                "observation": {
                    "provider": "open-meteo",
                    "observed_at": "2024-08-14T05:00",
                    "ambient_temp_c": 27.8,
                    "rainfall_mm_hour": 2.4,
                    "wind_speed_kmh": 18.0,
                    "visibility_m": 1500.0,
                },
                "risk_assessment": {
                    "domain": "weather",
                    "score": 0.33,
                    "summary": "Weather risk 0.33; exceedances: visibility_m.",
                    "features": {"visibility_m_exceeded": True},
                    "inputs_used": [
                        "ambient_temp_c",
                        "rainfall_mm_hour",
                        "visibility_m",
                        "wind_speed_kmh",
                    ],
                    "missing_inputs": [],
                },
            },
            "query_evidence": {"items": []},
            "get_evidence_gaps": {
                "missing_source_types": ["weather", "maintenance", "witness"],
                "missing_domain_inputs": [
                    "weather:visibility_m",
                    "weather:wind_speed_kmh",
                ],
            },
        },
    )

    assert "External weather service reports adverse conditions" in finding.hypothesis
    assert "No weather measurements available" not in finding.reasoning
    assert "Open-Meteo" in finding.reasoning
    assert finding.confidence > 0.25
    assert "weather" not in finding.missing_evidence
    assert not any(m.startswith("weather:visibility_m") for m in finding.missing_evidence)
    assert finding.domain_features is not None
    assert finding.domain_features["weather"]["score"] == 0.33
    assert any("external_weather_risk:" in s for s in finding.supporting_evidence)


def test_investigate_api_persists_ranked_findings(client, test_data_dir: Path):
    case_id = _create_case_with_signal(client, test_data_dir)

    # Rebuild timeline to populate anomalies used by signalling agent
    rebuild = client.post(f"/cases/{case_id}/timeline/rebuild")
    assert rebuild.status_code == 200

    run = client.post(
        f"/cases/{case_id}/investigate",
        json={"actor": "tester", "replace_existing": True},
    )
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["case_id"] == case_id
    assert body["run_id"]
    assert body["provider"]
    assert len(body["findings"]) >= 4  # four domain agents
    assert len(body["ranked"]) >= 4
    assert body["meta_summary"]

    findings = client.get(f"/cases/{case_id}/findings")
    assert findings.status_code == 200
    assert findings.json()["total"] >= 4

    hypotheses = client.get(f"/cases/{case_id}/hypotheses")
    assert hypotheses.status_code == 200
    ranked = hypotheses.json()["hypotheses"]
    assert len(ranked) >= 4
    scores = [h["weighted_score"] for h in ranked]
    assert scores == sorted(scores, reverse=True)

    case = client.get(f"/cases/{case_id}")
    assert case.status_code == 200
    assert case.json()["status"] == "investigating"


def test_mcp_tools_query_evidence(client, test_data_dir: Path, db_session):
    case_id = _create_case_with_signal(client, test_data_dir)
    import uuid

    tools = EvidenceTools(db_session, uuid.UUID(case_id))
    result = tools.query_evidence(source_type="signal_log", limit=5)
    assert result["total"] >= 1
    assert result["items"]
    gaps = tools.get_evidence_gaps()
    assert "missing_source_types" in gaps
    features = tools.get_domain_features()
    assert "domains" in features
