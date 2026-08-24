import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Case, CaseStatus
from app.schemas import CaseCreate
from app.services.audit import AuditService
from app.services.storage.repositories.case_repo import CaseRepository


class CaseService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CaseRepository(db)
        self.audit = AuditService(db)

    def create_case(self, payload: CaseCreate) -> Case:
        case = Case(
            title=payload.title,
            incident_time=payload.incident_time,
            location=payload.location,
            metadata_=payload.metadata,
            status=CaseStatus.OPEN,
        )
        self.repo.create(case)
        self.audit.log(
            case_id=case.case_id,
            entity_type="case",
            entity_id=case.case_id,
            action="case.created",
            payload={"title": case.title},
        )
        self.db.commit()
        self.db.refresh(case)
        return case

    def get_case(self, case_id: uuid.UUID) -> Case | None:
        return self.repo.get(case_id)

    def get_case_with_count(self, case_id: uuid.UUID) -> tuple[Case | None, int]:
        case = self.repo.get(case_id)
        if not case:
            return None, 0
        return case, self.repo.evidence_count(case_id)
