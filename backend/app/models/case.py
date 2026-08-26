import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utcnow
from app.models.enums import CaseStatus

class Case(Base, TimestampMixin):
    __tablename__ = "cases"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    incident_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    location: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, name="case_status", native_enum=False),
        default=CaseStatus.OPEN,
        nullable=False,
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    evidence_artifacts = relationship(
        "EvidenceArtifact", back_populates="case", cascade="all, delete-orphan"
    )
    audit_events = relationship(
        "AuditEvent", back_populates="case", cascade="all, delete-orphan"
    )
    events = relationship(
        "Event", back_populates="case", cascade="all, delete-orphan"
    )
    anomalies = relationship(
        "Anomaly", back_populates="case", cascade="all, delete-orphan"
    )
    conflicts = relationship(
        "EvidenceConflict", back_populates="case", cascade="all, delete-orphan"
    )
