import hashlib
import os
import shutil
import uuid
from pathlib import Path

from app.core.config import settings


class FileStore:
    def __init__(
        self,
        raw_root: Path | None = None,
        processed_root: Path | None = None,
    ) -> None:
        self.raw_root = (raw_root or settings.evidence_storage_path).resolve()
        self.processed_root = (
            processed_root or settings.processed_storage_path
        ).resolve()
        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.processed_root.mkdir(parents=True, exist_ok=True)

    def store_raw(
        self,
        case_id: uuid.UUID,
        evidence_id: uuid.UUID,
        filename: str,
        content: bytes,
    ) -> str:
        dest_dir = self.raw_root / str(case_id) / str(evidence_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename
        if dest_path.exists():
            raise FileExistsError(f"Evidence file already exists: {dest_path}")

        temp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
        temp_path.write_bytes(content)
        os.replace(temp_path, dest_path)
        return str(dest_path.relative_to(self.raw_root.parent))

    def read_raw(self, storage_path: str) -> bytes:
        path = self._resolve_storage_path(storage_path)
        return path.read_bytes()

    def verify_hash(self, storage_path: str, expected_sha256: str) -> bool:
        content = self.read_raw(storage_path)
        actual = hashlib.sha256(content).hexdigest()
        return actual == expected_sha256

    def write_manifest(
        self,
        case_id: uuid.UUID,
        evidence_id: uuid.UUID,
        manifest: dict,
    ) -> Path:
        dest_dir = self.processed_root / str(case_id) / str(evidence_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = dest_dir / "manifest.json"
        import json

        manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
        return manifest_path

    def _resolve_storage_path(self, storage_path: str) -> Path:
        path = Path(storage_path)
        if not path.is_absolute():
            path = (self.raw_root.parent / storage_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Evidence file not found: {path}")
        return path

    def absolute_raw_path(self, storage_path: str) -> Path:
        return self._resolve_storage_path(storage_path)
