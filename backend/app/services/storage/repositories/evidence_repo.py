import json
import uuid
from typing import Any

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models import EvidenceArtifact, EvidenceRecord
from app.models.enums import SourceType


class EvidenceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_artifact(self, artifact: EvidenceArtifact) -> EvidenceArtifact:
        self.db.add(artifact)
        self.db.flush()
        return artifact

    def get_artifact(self, evidence_id: uuid.UUID) -> EvidenceArtifact | None:
        return self.db.get(EvidenceArtifact, evidence_id)

    def get_record(self, record_id: uuid.UUID) -> EvidenceRecord | None:
        return self.db.get(EvidenceRecord, record_id)

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
        stmt = (
            select(EvidenceArtifact)
            .where(EvidenceArtifact.case_id == case_id)
            .order_by(EvidenceArtifact.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def search_records(
        self,
        case_id: uuid.UUID,
        *,
        evidence_id: uuid.UUID | None = None,
        source_type: SourceType | None = None,
        is_valid: bool | None = None,
        has_warnings: bool | None = None,
        q: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[tuple[EvidenceRecord, EvidenceArtifact]], int]:
        """Return matching records with parent artifact and total count."""
        filters: list[Any] = [EvidenceRecord.case_id == case_id]
        if evidence_id is not None:
            filters.append(EvidenceRecord.evidence_id == evidence_id)
        if is_valid is not None:
            filters.append(EvidenceRecord.is_valid.is_(is_valid))
        if has_warnings is True:
            filters.append(EvidenceRecord.parse_warnings.isnot(None))
        elif has_warnings is False:
            filters.append(EvidenceRecord.parse_warnings.is_(None))
        if source_type is not None:
            filters.append(EvidenceArtifact.source_type == source_type)
        if q and q.strip():
            needle = f"%{q.strip().lower()}%"
            # Dialect-portable text search over JSON payloads.
            filters.append(
                or_(
                    cast(EvidenceRecord.normalized_data, String).ilike(needle),
                    cast(EvidenceRecord.raw_data, String).ilike(needle),
                    EvidenceArtifact.filename.ilike(needle),
                )
            )

        base = (
            select(EvidenceRecord, EvidenceArtifact)
            .join(
                EvidenceArtifact,
                EvidenceRecord.evidence_id == EvidenceArtifact.evidence_id,
            )
            .where(*filters)
        )
        count_stmt = select(func.count()).select_from(base.subquery())
        total = self.db.scalar(count_stmt) or 0

        stmt = (
            base.order_by(
                EvidenceArtifact.filename.asc(),
                EvidenceRecord.record_index.asc(),
            )
            .offset(max(offset, 0))
            .limit(max(1, min(limit, 500)))
        )
        rows = list(self.db.execute(stmt).all())
        return [(row[0], row[1]) for row in rows], total

    @staticmethod
    def record_matches_query(record: EvidenceRecord, q: str) -> bool:
        """In-memory fallback used by tests / non-SQL backends if needed."""
        needle = q.strip().lower()
        if not needle:
            return True
        blob = json.dumps(
            {"raw": record.raw_data, "normalized": record.normalized_data},
            default=str,
        ).lower()
        return needle in blob
