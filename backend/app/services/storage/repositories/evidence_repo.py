import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import EvidenceArtifact, EvidenceRecord


class EvidenceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_artifact(self, artifact: EvidenceArtifact) -> EvidenceArtifact:
        self.db.add(artifact)
        self.db.flush()
        return artifact

    def get_artifact(self, evidence_id: uuid.UUID) -> EvidenceArtifact | None:
        return self.db.get(EvidenceArtifact, evidence_id)

    def update_artifact(self, artifact: EvidenceArtifact) -> EvidenceArtifact:
        self.db.flush()
        return artifact

    def find_by_sha256_for_case(
        self, case_id: uuid.UUID, sha256: str
    ) -> EvidenceArtifact | None:
        stmt = select(EvidenceArtifact).where(
            EvidenceArtifact.case_id == case_id,
            EvidenceArtifact.sha256 == sha256,
        )
        return self.db.scalar(stmt)

    def bulk_create_records(self, records: list[EvidenceRecord]) -> None:
        self.db.add_all(records)
        self.db.flush()

    def record_stats(self, evidence_id: uuid.UUID) -> tuple[int, int, int]:
        total_stmt = select(func.count()).where(
            EvidenceRecord.evidence_id == evidence_id
        )
        invalid_stmt = select(func.count()).where(
            EvidenceRecord.evidence_id == evidence_id,
            EvidenceRecord.is_valid.is_(False),
        )
        warning_stmt = select(func.count()).where(
            EvidenceRecord.evidence_id == evidence_id,
            EvidenceRecord.parse_warnings.isnot(None),
        )
        total = self.db.scalar(total_stmt) or 0
        invalid = self.db.scalar(invalid_stmt) or 0
        warnings = self.db.scalar(warning_stmt) or 0
        return total, invalid, warnings

    def list_records_for_evidence(
        self, evidence_id: uuid.UUID, *, valid_only: bool = False
    ) -> list[EvidenceRecord]:
        stmt = (
            select(EvidenceRecord)
            .where(EvidenceRecord.evidence_id == evidence_id)
            .order_by(EvidenceRecord.record_index)
        )
        if valid_only:
            stmt = stmt.where(EvidenceRecord.is_valid.is_(True))
        return list(self.db.scalars(stmt).all())

    def list_artifacts_for_case(self, case_id: uuid.UUID) -> list[EvidenceArtifact]:
        stmt = select(EvidenceArtifact).where(EvidenceArtifact.case_id == case_id)
        return list(self.db.scalars(stmt).all())
