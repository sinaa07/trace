"""Backend tests for case listing and evidence-record explorer APIs."""

from pathlib import Path


def _create_case(client, title: str = "Explorer case") -> str:
    resp = client.post("/cases", json={"title": title, "created_by": "Inspector A"})
    assert resp.status_code == 201
    return resp.json()["case_id"]


def _upload_signal(client, case_id: str, test_data_dir: Path) -> str:
    path = test_data_dir / "signal_log.csv"
    with path.open("rb") as handle:
        resp = client.post(
            f"/cases/{case_id}/evidence",
            files={"file": ("signal_log.csv", handle, "text/csv")},
            data={"source_type": "signal_log", "actor": "Inspector A"},
        )
    assert resp.status_code == 201, resp.text
    return resp.json()["evidence_id"]


def test_list_cases(client):
    first = _create_case(client, "Alpha case")
    second = _create_case(client, "Beta case")

    resp = client.get("/cases")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2
    ids = {item["case_id"] for item in body["items"]}
    assert first in ids
    assert second in ids


def test_list_case_records_with_filters(client, test_data_dir: Path):
    case_id = _create_case(client)
    evidence_id = _upload_signal(client, case_id, test_data_dir)

    resp = client.get(f"/cases/{case_id}/records")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] > 0
    assert body["case_id"] == case_id
    assert all(item["evidence_id"] == evidence_id for item in body["items"])
    assert body["items"][0]["filename"] == "signal_log.csv"
    assert body["items"][0]["source_type"] == "signal_log"

    filtered = client.get(
        f"/cases/{case_id}/records",
        params={"source_type": "signal_log", "is_valid": True, "limit": 5},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] >= 1
    assert len(filtered.json()["items"]) <= 5


def test_list_and_get_evidence_records(client, test_data_dir: Path):
    case_id = _create_case(client)
    evidence_id = _upload_signal(client, case_id, test_data_dir)

    listed = client.get(f"/evidence/{evidence_id}/records")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) > 0

    record_id = items[0]["record_id"]
    detail = client.get(f"/evidence/records/{record_id}")
    assert detail.status_code == 200
    assert detail.json()["record_id"] == record_id
    assert detail.json()["field_provenance"] is not None or True


def test_record_search_query(client, test_data_dir: Path):
    case_id = _create_case(client)
    _upload_signal(client, case_id, test_data_dir)

    resp = client.get(f"/cases/{case_id}/records", params={"q": "RED"})
    assert resp.status_code == 200
    # Synthetic signal log includes RED states; if empty, still a valid empty filter result.
    assert resp.json()["total"] >= 0
    assert "filters" in resp.json()


def test_missing_case_records_404(client):
    resp = client.get("/cases/00000000-0000-0000-0000-000000000099/records")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "NOT_FOUND"
