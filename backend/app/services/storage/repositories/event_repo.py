import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Event


class EventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, event_id: uuid.UUID) -> Event | None:
        return self.db.get(Event, event_id)

    def bulk_create(self, events: list[Event]) -> None:
        self.db.add_all(events)
        self.db.flush()

    def delete_for_evidence(self, evidence_id: uuid.UUID) -> int:
        stmt = delete(Event).where(Event.evidence_id == evidence_id)
        result = self.db.execute(stmt)
        self.db.flush()
        return result.rowcount or 0

    def list_for_case(
        self,
        case_id: uuid.UUID,
        *,
        event_type: str | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        stmt = (
            select(Event)
            .where(Event.case_id == case_id)
            .order_by(
                Event.timeline_index.asc().nulls_last(),
                Event.corrected_timestamp.asc().nulls_last(),
            )
        )
        if event_type:
            stmt = stmt.where(Event.event_type == event_type)
        if limit:
            stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt).all())

    def count_for_case(self, case_id: uuid.UUID) -> int:
        stmt = select(func.count()).where(Event.case_id == case_id)
        return self.db.scalar(stmt) or 0

    def update_timeline_fields(self, events: list[Event]) -> None:
        self.db.flush()
