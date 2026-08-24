from pathlib import Path

from app.services.provenance import ProvenanceService
from app.services.storage.file_store import FileStore


def test_file_store_roundtrip(storage_paths, tmp_path):
    raw_path, _ = storage_paths
    store = FileStore(raw_root=raw_path, processed_root=storage_paths[1])
    case_id = "11111111-1111-1111-1111-111111111111"
    evidence_id = "22222222-2222-2222-2222-222222222222"
    content = b"test evidence bytes"

    rel_path = store.store_raw(case_id, evidence_id, "sample.csv", content)
    sha = ProvenanceService.compute_sha256(content)
    assert store.verify_hash(rel_path, sha)

    manifest_path = store.write_manifest(
        case_id,
        evidence_id,
        {"record_count": 1},
    )
    assert manifest_path.exists()
