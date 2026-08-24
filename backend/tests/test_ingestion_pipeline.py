import json
from pathlib import Path


def _create_case(client) -> str:
    resp = client.post("/cases", json={"title": "Ingestion E2E"})
    assert resp.status_code == 201
    return resp.json()["case_id"]


def test_upload_csv_evidence(client, test_data_dir: Path):
    case_id = _create_case(client)
    csv_path = test_data_dir / "signal_log.csv"
    with csv_path.open("rb") as f:
        resp = client.post(
            f"/cases/{case_id}/evidence",
            data={"source_type": "signal_log"},
            files={"file": ("signal_log.csv", f, "text/csv")},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["processing_status"] == "completed"
    assert body["record_count"] == 3
    assert len(body["sha256"]) == 64
    assert body["profile_id"] == "signal_log_v1"
    assert body["needs_review"] is False
    assert body["match_score"] is not None

    get_resp = client.get(f"/evidence/{body['evidence_id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["record_count"] == 3
    assert get_resp.json()["profile_id"] == "signal_log_v1"


def test_upload_json_evidence(client, test_data_dir: Path):
    case_id = _create_case(client)
    json_path = test_data_dir / "train_telemetry.json"
    metadata = json.dumps({"timezone": "Asia/Kolkata"})
    with json_path.open("rb") as f:
        resp = client.post(
            f"/cases/{case_id}/evidence",
            data={"source_type": "train_telemetry", "source_metadata": metadata},
            files={"file": ("train_telemetry.json", f, "application/json")},
        )
    assert resp.status_code == 201
    assert resp.json()["record_count"] == 2


def test_duplicate_hash_rejected(client, test_data_dir: Path):
    case_id = _create_case(client)
    csv_path = test_data_dir / "signal_log.csv"
    for _ in range(2):
        with csv_path.open("rb") as f:
            resp = client.post(
                f"/cases/{case_id}/evidence",
                data={"source_type": "signal_log"},
                files={"file": ("signal_log.csv", f, "text/csv")},
            )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"]["code"] == "DUPLICATE_HASH"


def test_malformed_csv_still_ingested(client, test_data_dir: Path):
    case_id = _create_case(client)
    bad_path = test_data_dir / "malformed" / "missing_columns.csv"
    with bad_path.open("rb") as f:
        resp = client.post(
            f"/cases/{case_id}/evidence",
            data={"source_type": "signal_log"},
            files={"file": ("missing_columns.csv", f, "text/csv")},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["record_count"] >= 1
    assert body["invalid_record_count"] >= 1
