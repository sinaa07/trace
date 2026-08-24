import hashlib
from datetime import datetime, timezone
from typing import BinaryIO

from app.models.base import utcnow


class ProvenanceService:
    @staticmethod
    def compute_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def compute_sha256_stream(stream: BinaryIO) -> str:
        digest = hashlib.sha256()
        while chunk := stream.read(8192):
            digest.update(chunk)
        stream.seek(0)
        return digest.hexdigest()

    @staticmethod
    def initial_custody_entry(sha256: str, actor: str = "system") -> list[dict]:
        return [
            {
                "action": "uploaded",
                "actor": actor,
                "timestamp": utcnow().isoformat(),
                "sha256": sha256,
            }
        ]

    @staticmethod
    def append_custody_entry(
        history: list[dict],
        action: str,
        sha256: str,
        actor: str = "system",
    ) -> list[dict]:
        entry = {
            "action": action,
            "actor": actor,
            "timestamp": utcnow().isoformat(),
            "sha256": sha256,
        }
        return [*history, entry]
