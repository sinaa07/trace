import uuid

from sqlalchemy.orm import Session

from app.models import EvidenceArtifact
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

    def list_for_case(self, case_id: uuid.UUID) -> list[EvidenceArtifact]:
        return self.repo.list_artifacts_for_case(case_id)

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
