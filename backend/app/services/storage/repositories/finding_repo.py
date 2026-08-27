"""Persistence for hypothesis findings."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.finding import HypothesisFinding


class FindingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, finding: HypothesisFinding) -> HypothesisFinding:
        self.db.add(finding)
        self.db.flush()
        return finding

    def list_for_case(self, case_id: uuid.UUID) -> list[HypothesisFinding]:
        stmt = (
            select(HypothesisFinding)
            .where(HypothesisFinding.case_id == case_id)
            .order_by(
                HypothesisFinding.rank_score.desc(),
                HypothesisFinding.created_at.desc(),
            )
        )
        rows = list(self.db.scalars(stmt).all())
        # Null rank_score last (portable across SQLite/Postgres)
        return sorted(
            rows,
            key=lambda r: (
                r.rank_score is None,
                -(r.rank_score or 0.0),
                -(r.created_at.timestamp() if r.created_at else 0.0),
            ),
        )

    def delete_for_case(self, case_id: uuid.UUID) -> int:
        result = self.db.execute(
            delete(HypothesisFinding).where(HypothesisFinding.case_id == case_id)
        )
        self.db.flush()
        return int(result.rowcount or 0)

    def get(self, finding_id: uuid.UUID) -> HypothesisFinding | None:
        return self.db.get(HypothesisFinding, finding_id)
