from app.services.provenance import ProvenanceService


def test_sha256_and_custody():
    content = b"railway evidence sample"
    sha = ProvenanceService.compute_sha256(content)
    assert len(sha) == 64

    history = ProvenanceService.initial_custody_entry(sha)
    assert history[0]["action"] == "uploaded"
    assert history[0]["sha256"] == sha

    updated = ProvenanceService.append_custody_entry(history, "parsed", sha)
    assert len(updated) == 2
    assert updated[-1]["action"] == "parsed"
