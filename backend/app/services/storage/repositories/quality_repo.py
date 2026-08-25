import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Anomaly, EvidenceConflict


class QualityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def replace_anomalies(self, case_id: uuid.UUID, anomalies: list[Anomaly]) -> None:
        self.db.execute(delete(Anomaly).where(Anomaly.case_id == case_id))
        if anomalies:
            self.db.add_all(anomalies)
        self.db.flush()

    def replace_conflicts(
        self, case_id: uuid.UUID, conflicts: list[EvidenceConflict]
    ) -> None:
        self.db.execute(delete(EvidenceConflict).where(EvidenceConflict.case_id == case_id))
        if conflicts:
            self.db.add_all(conflicts)
        self.db.flush()

    def list_anomalies(self, case_id: uuid.UUID) -> list[Anomaly]:
        stmt = (
            select(Anomaly)
            .where(Anomaly.case_id == case_id)
            .order_by(Anomaly.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_conflicts(self, case_id: uuid.UUID) -> list[EvidenceConflict]:
        stmt = (
            select(EvidenceConflict)
            .where(EvidenceConflict.case_id == case_id)
            .order_by(EvidenceConflict.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())
