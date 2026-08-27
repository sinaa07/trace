import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Case, CaseStatus


class CaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, case: Case) -> Case:
        self.db.add(case)
        self.db.flush()
        return case

    def get(self, case_id: uuid.UUID) -> Case | None:
        return self.db.get(Case, case_id)

    def list_cases(self, *, limit: int = 100, offset: int = 0) -> list[Case]:
        stmt = (
            select(Case)
            .order_by(Case.created_at.desc())
            .offset(max(offset, 0))
            .limit(max(1, min(limit, 500)))
        )
        return list(self.db.scalars(stmt).all())

    def count_cases(self) -> int:
        return self.db.scalar(select(func.count()).select_from(Case)) or 0

    def update_status(self, case: Case, status: CaseStatus) -> Case:
        case.status = status
        self.db.flush()
        return case

    def evidence_count(self, case_id: uuid.UUID) -> int:
        from app.models import EvidenceArtifact

        stmt = select(func.count()).where(EvidenceArtifact.case_id == case_id)
        return self.db.scalar(stmt) or 0
