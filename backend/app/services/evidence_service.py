import uuid

from sqlalchemy.orm import Session

from app.models import EvidenceArtifact, EvidenceRecord
from app.models.enums import SourceType
from app.schemas import EvidenceRecordResponse
from app.services.audit import AuditService
from app.services.event_service import EventService
from app.services.storage.repositories.evidence_repo import EvidenceRepository


class EvidenceDeleteForbiddenError(Exception):
    """Raised when the uploader attempts to delete their own evidence."""


class EvidenceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = EvidenceRepository(db)
        self.audit = AuditService(db)
        self.event_service = EventService(db)

    @staticmethod
    def get_uploader(artifact: EvidenceArtifact) -> str:
        for entry in artifact.custody_history or []:
            if entry.get("action") == "uploaded":
                return str(entry.get("actor", "system"))
        return "system"

    @staticmethod
    def _to_record_response(
        record: EvidenceRecord, artifact: EvidenceArtifact | None = None
    ) -> EvidenceRecordResponse:
        response = EvidenceRecordResponse.model_validate(record)
        if artifact is not None:
            response.filename = artifact.filename
            response.source_type = artifact.source_type
            response.sha256 = artifact.sha256
        return response

    def list_for_case(self, case_id: uuid.UUID) -> list[EvidenceArtifact]:
        return self.repo.list_artifacts_for_case(case_id)

    def get_record(self, record_id: uuid.UUID) -> EvidenceRecordResponse | None:
        record = self.repo.get_record(record_id)
        if not record:
            return None
        artifact = self.repo.get_artifact(record.evidence_id)
        return self._to_record_response(record, artifact)

    def search_case_records(
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
    ) -> tuple[list[EvidenceRecordResponse], int]:
        rows, total = self.repo.search_records(
            case_id,
            evidence_id=evidence_id,
            source_type=source_type,
            is_valid=is_valid,
            has_warnings=has_warnings,
            q=q,
            limit=limit,
            offset=offset,
        )
        items = [self._to_record_response(record, artifact) for record, artifact in rows]
        return items, total

    def list_artifact_records(
        self,
        evidence_id: uuid.UUID,
        *,
        valid_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[EvidenceArtifact | None, list[EvidenceRecordResponse], int]:
        artifact = self.repo.get_artifact(evidence_id)
        if not artifact:
            return None, [], 0
        records = self.repo.list_records_for_evidence(
            evidence_id, valid_only=valid_only
        )
        total = len(records)
        sliced = records[max(offset, 0) : max(offset, 0) + max(1, min(limit, 500))]
        items = [self._to_record_response(r, artifact) for r in sliced]
        return artifact, items, total

    def delete_evidence(self, evidence_id: uuid.UUID, actor: str) -> uuid.UUID:
        artifact = self.repo.get_artifact(evidence_id)
        if not artifact:
            raise ValueError(f"Evidence not found: {evidence_id}")

        uploader = self.get_uploader(artifact)
        if actor.strip() == uploader:
            raise EvidenceDeleteForbiddenError(
                "Uploader cannot delete their own evidence; chain-of-custody requires a different investigator"
            )

        case_id = artifact.case_id
        self.audit.log(
            case_id=case_id,
            entity_type="evidence_artifact",
            entity_id=evidence_id,
            action="evidence.deleted",
            payload={
                "filename": artifact.filename,
                "sha256": artifact.sha256,
                "uploader": uploader,
                "deleted_by": actor,
                "custody_history": artifact.custody_history,
            },
            actor=actor,
        )
        self.db.delete(artifact)
        self.db.commit()
        self.event_service.rebuild_case_timeline(case_id)
        return case_id
