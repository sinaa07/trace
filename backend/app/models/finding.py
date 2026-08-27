"""Persisted HypothesisFinding rows from Phase 3 investigation agents."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utcnow


class HypothesisFinding(Base, TimestampMixin):
    __tablename__ = "hypothesis_findings"

    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.case_id"), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    contradicting_evidence: Mapped[list] = mapped_column(
        JSONB, default=list, nullable=False
    )
    relevant_events: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    missing_evidence: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    assumptions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    reasoning_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    uncertainty: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain_features: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rank_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank_dimensions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    case = relationship("Case", back_populates="findings")
