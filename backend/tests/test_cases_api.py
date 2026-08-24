def test_create_and_get_case(client):
    create_resp = client.post(
        "/cases",
        json={"title": "Test derailment", "location": {"track": "T12"}},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["title"] == "Test derailment"
    assert body["status"] == "open"
    assert body["evidence_count"] == 0

    case_id = body["case_id"]
    get_resp = client.get(f"/cases/{case_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["case_id"] == case_id


def test_get_missing_case_returns_404(client):
    resp = client.get("/cases/00000000-0000-0000-0000-000000000099")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "NOT_FOUND"
