import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.case_id"), nullable=False, index=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_artifacts.evidence_id"),
        nullable=False,
        index=True,
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_records.record_id"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    raw_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    corrected_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    temporal_confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    clock_offset_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    location: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    timeline_index: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    case = relationship("Case", back_populates="events")
    artifact = relationship("EvidenceArtifact", back_populates="events")
    record = relationship("EvidenceRecord", back_populates="events")
