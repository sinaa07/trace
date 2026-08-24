import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ProcessingStatus, SourceType


class EvidenceArtifact(Base, TimestampMixin):
    __tablename__ = "evidence_artifacts"

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.case_id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type", native_enum=False), nullable=False
    )
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    acquisition_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status", native_enum=False),
        default=ProcessingStatus.PENDING,
        nullable=False,
        index=True,
    )
    parser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_reasons: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    custody_history: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    case = relationship("Case", back_populates="evidence_artifacts")
    records = relationship(
        "EvidenceRecord", back_populates="artifact", cascade="all, delete-orphan"
    )
    events = relationship(
        "Event", back_populates="artifact", cascade="all, delete-orphan"
    )


class EvidenceRecord(Base, TimestampMixin):
    __tablename__ = "evidence_records"

    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_artifacts.evidence_id"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.case_id"), nullable=False, index=True
    )
    record_index: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    normalized_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    field_provenance: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    parse_warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    artifact = relationship("EvidenceArtifact", back_populates="records")
    events = relationship(
        "Event", back_populates="record", cascade="all, delete-orphan"
    )
