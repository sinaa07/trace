"""API test for domain-features endpoint."""

from datetime import datetime, timezone


def test_domain_features_endpoint(client):
    create = client.post(
        "/cases",
        json={
            "title": "Scorer case",
            "incident_time": datetime(2024, 6, 1, 3, 15, tzinfo=timezone.utc).isoformat(),
            "metadata": {
                "duty": {"duty_hours": 11},
                "weather": {"visibility_m": 150, "wind_speed_kmh": 20},
            },
            "created_by": "Inspector A",
        },
    )
    assert create.status_code == 201
    case_id = create.json()["case_id"]

    resp = client.get(f"/cases/{case_id}/domain-features")
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == case_id
    domains = {d["domain"] for d in body["domains"]}
    assert {"fatigue", "behavioral_telemetry", "signalling", "track", "weather"} <= domains
    fatigue = next(d for d in body["domains"] if d["domain"] == "fatigue")
    assert fatigue["score"] is not None
    weather = next(d for d in body["domains"] if d["domain"] == "weather")
    assert weather["features"].get("visibility_m_exceeded") is True


def test_domain_features_missing_case(client):
    resp = client.get("/cases/00000000-0000-0000-0000-000000000099/domain-features")
    assert resp.status_code == 404
