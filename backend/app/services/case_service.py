import uuid

from sqlalchemy.orm import Session

from app.models import Case, CaseStatus
from app.schemas import CaseCreate, CaseUpdate
from app.services.audit import AuditService
from app.services.storage.repositories.case_repo import CaseRepository


class CaseService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CaseRepository(db)
        self.audit = AuditService(db)

    def create_case(self, payload: CaseCreate) -> Case:
        metadata = dict(payload.metadata or {})
        if payload.created_by:
            metadata["created_by"] = payload.created_by

        case = Case(
            title=payload.title,
            incident_time=payload.incident_time,
            location=payload.location,
            metadata_=metadata or None,
            status=CaseStatus.OPEN,
        )
        self.repo.create(case)
        self.audit.log(
            case_id=case.case_id,
            entity_type="case",
            entity_id=case.case_id,
            action="case.created",
            payload={"title": case.title, "created_by": payload.created_by},
            actor=payload.created_by or "system",
        )
        self.db.commit()
        self.db.refresh(case)
        return case

    def update_case(self, case_id: uuid.UUID, payload: CaseUpdate) -> Case | None:
        case = self.repo.get(case_id)
        if not case:
            return None

        if payload.title is not None:
            case.title = payload.title
        if payload.incident_time is not None:
            case.incident_time = payload.incident_time
        if payload.location is not None:
            case.location = payload.location
        if payload.metadata is not None:
            merged = dict(case.metadata_ or {})
            merged.update(payload.metadata)
            case.metadata_ = merged

        self.audit.log(
            case_id=case.case_id,
            entity_type="case",
            entity_id=case.case_id,
            action="case.updated",
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
