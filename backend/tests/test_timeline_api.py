from pathlib import Path


def _create_case(client, *, incident_time: str | None = None) -> str:
    payload = {"title": "Timeline E2E"}
    if incident_time:
        payload["incident_time"] = incident_time
    resp = client.post("/cases", json=payload)
    assert resp.status_code == 201
    return resp.json()["case_id"]


def test_ingest_creates_events_and_timeline(client, test_data_dir: Path):
    case_id = _create_case(
        client, incident_time="2024-03-15T08:12:00+00:00"
    )
    csv_path = test_data_dir / "signal_log.csv"
    with csv_path.open("rb") as f:
        resp = client.post(
            f"/cases/{case_id}/evidence",
            data={"source_type": "signal_log"},
            files={"file": ("signal_log.csv", f, "text/csv")},
        )
    assert resp.status_code == 201

    events_resp = client.get(f"/cases/{case_id}/events")
    assert events_resp.status_code == 200
    events_body = events_resp.json()
    assert events_body["event_count"] >= 2
    assert all(e["event_type"] == "SIGNAL_STATE_CHANGE" for e in events_body["events"])

    timeline_resp = client.get(f"/cases/{case_id}/timeline")
    assert timeline_resp.status_code == 200
    timeline = timeline_resp.json()
    assert timeline["event_count"] == events_body["event_count"]
    indices = [e["timeline_index"] for e in timeline["events"]]
    assert indices == sorted(indices)


def test_timeline_rebuild_endpoint(client, test_data_dir: Path):
    case_id = _create_case(client)
    json_path = test_data_dir / "train_telemetry.json"
    with json_path.open("rb") as f:
        client.post(
            f"/cases/{case_id}/evidence",
            data={"source_type": "train_telemetry"},
            files={"file": ("train_telemetry.json", f, "application/json")},
        )

    rebuild = client.post(f"/cases/{case_id}/timeline/rebuild")
    assert rebuild.status_code == 200
    body = rebuild.json()
    assert body["event_count"] >= 2
    assert body["rebuilt_at"] is not None


def test_events_filter_by_type(client, test_data_dir: Path):
    case_id = _create_case(client)
    json_path = test_data_dir / "train_telemetry.json"
    with json_path.open("rb") as f:
        client.post(
            f"/cases/{case_id}/evidence",
            data={"source_type": "train_telemetry"},
            files={"file": ("train_telemetry.json", f, "application/json")},
        )

    resp = client.get(f"/cases/{case_id}/events?event_type=SPEED_SAMPLE")
    assert resp.status_code == 200
    for event in resp.json()["events"]:
        assert event["event_type"] == "SPEED_SAMPLE"
