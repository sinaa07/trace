"""Tests for evidence list and delete chain-of-custody rules."""
from pathlib import Path

def test_list_case_evidence(client, test_data_dir: Path):
    create_resp = client.post(
        "/cases",
        json={"title": "List evidence case", "created_by": "investigator_a"},
    )
    case_id = create_resp.json()["case_id"]

    csv_path = test_data_dir / "signal_log.csv"
    with csv_path.open("rb") as handle:
        upload_resp = client.post(
            f"/cases/{case_id}/evidence",
            data={"source_type": "signal_log", "actor": "investigator_a"},
            files={"file": ("signal_log.csv", handle, "text/csv")},
        )
    assert upload_resp.status_code == 201

    list_resp = client.get(f"/cases/{case_id}/evidence")
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] == 1
    assert body["items"][0]["filename"] == "signal_log.csv"
    assert body["items"][0]["custody_history"][0]["actor"] == "investigator_a"


def test_uploader_cannot_delete_own_evidence(client, test_data_dir: Path):
    create_resp = client.post("/cases", json={"title": "Delete guard case"})
    case_id = create_resp.json()["case_id"]

    csv_path = test_data_dir / "signal_log.csv"
    with csv_path.open("rb") as handle:
        upload_resp = client.post(
            f"/cases/{case_id}/evidence",
            data={"source_type": "signal_log", "actor": "investigator_a"},
            files={"file": ("signal_log.csv", handle, "text/csv")},
        )
    evidence_id = upload_resp.json()["evidence_id"]

    delete_resp = client.delete(
        f"/evidence/{evidence_id}",
        params={"actor": "investigator_a"},
    )
    assert delete_resp.status_code == 403
    assert delete_resp.json()["detail"]["error"]["code"] == "FORBIDDEN"


def test_other_investigator_can_delete_evidence(client, test_data_dir: Path):
    create_resp = client.post("/cases", json={"title": "Delete allowed case"})
    case_id = create_resp.json()["case_id"]

    csv_path = test_data_dir / "signal_log.csv"
    with csv_path.open("rb") as handle:
        upload_resp = client.post(
            f"/cases/{case_id}/evidence",
            data={"source_type": "signal_log", "actor": "investigator_a"},
            files={"file": ("signal_log.csv", handle, "text/csv")},
        )
    evidence_id = upload_resp.json()["evidence_id"]

    delete_resp = client.delete(
        f"/evidence/{evidence_id}",
        params={"actor": "supervisor_b"},
    )
    assert delete_resp.status_code == 204

    list_resp = client.get(f"/cases/{case_id}/evidence")
    assert list_resp.json()["total"] == 0
