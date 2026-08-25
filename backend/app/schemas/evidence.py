from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CaseStatus, ProcessingStatus, SourceType


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    incident_time: datetime | None = None
    location: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    created_by: str | None = Field(default=None, max_length=256)


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    incident_time: datetime | None = None
    location: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    case_id: UUID
    title: str
    incident_time: datetime | None
    location: dict[str, Any] | None
    status: CaseStatus
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="metadata_")
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    evidence_count: int = 0


class EvidenceSummary(BaseModel):
    evidence_id: UUID
    filename: str
    source_type: SourceType
    processing_status: ProcessingStatus
    record_count: int = 0


class EvidenceUploadMetadata(BaseModel):
    source_system: str | None = None
    operator: str | None = None
    device_id: str | None = None
    timezone: str | None = None
    acquisition_time: datetime | None = None
    extra: dict[str, Any] | None = None


class EvidenceArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evidence_id: UUID
    case_id: UUID
    filename: str
    source_type: SourceType
    file_size: int
    sha256: str
    acquisition_time: datetime
    source_metadata: dict[str, Any] | None
    processing_status: ProcessingStatus
    parser_version: str | None
    profile_id: str | None = None
    match_score: float | None = None
    match_reasons: list[str] | None = None
    needs_review: bool = False
    custody_history: list[dict[str, Any]]
    storage_path: str
    error_detail: str | None
    created_at: datetime
    record_count: int = 0
    warning_count: int = 0
    invalid_record_count: int = 0


class EvidenceListResponse(BaseModel):
    case_id: UUID
    items: list[EvidenceArtifactResponse]
    total: int


class EvidenceRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    record_id: UUID
    evidence_id: UUID
    case_id: UUID
    record_index: int
    raw_data: dict[str, Any]
    normalized_data: dict[str, Any]
    field_provenance: list[dict[str, Any]] | None
    parse_warnings: list[str] | None
    is_valid: bool
    created_at: datetime


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
