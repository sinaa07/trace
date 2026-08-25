from pathlib import Path


def _create_case(client, *, incident_time: str | None = None) -> str:
    payload = {"title": "Quality analysis case"}
    if incident_time:
        payload["incident_time"] = incident_time
    resp = client.post("/cases", json=payload)
    assert resp.status_code == 201
    return resp.json()["case_id"]


def test_conflicting_signal_logs_detected(client, test_data_dir: Path):
    case_id = _create_case(
        client, incident_time="2024-03-15T08:12:00+00:00"
    )
    for filename in ("signal_log_a.csv", "signal_log_b.csv"):
        path = test_data_dir / "conflicting" / filename
        with path.open("rb") as f:
            resp = client.post(
                f"/cases/{case_id}/evidence",
                data={"source_type": "signal_log"},
                files={"file": (filename, f, "text/csv")},
            )
        assert resp.status_code == 201, resp.text

    conflict_resp = client.get(f"/cases/{case_id}/conflicts")
    assert conflict_resp.status_code == 200
    body = conflict_resp.json()
    assert body["conflict_count"] >= 1
    assert body["conflicts"][0]["conflict_type"] == "signal_state_mismatch"


def test_high_speed_anomaly_detected(client, test_data_dir: Path):
    case_id = _create_case(client)
    path = test_data_dir / "anomaly_high_speed.json"
    with path.open("rb") as f:
        resp = client.post(
            f"/cases/{case_id}/evidence",
            data={"source_type": "train_telemetry"},
            files={"file": ("train_telemetry_high_speed.json", f, "application/json")},
        )
    assert resp.status_code == 201

    anomaly_resp = client.get(f"/cases/{case_id}/anomalies")
    assert anomaly_resp.status_code == 200
    body = anomaly_resp.json()
    assert body["anomaly_count"] >= 1
    assert any(
        a["rule_id"] == "speed_threshold_exceeded" for a in body["anomalies"]
    )
