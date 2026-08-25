from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.quality import AnomalySeverity, ConflictSeverity


class AnomalyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    anomaly_id: UUID
    case_id: UUID
    rule_id: str
    severity: AnomalySeverity
    title: str
    explanation: str
    affected_event_ids: list[str]
    evidence_refs: list[str]
    details: dict[str, Any] | None
    created_at: datetime


class ConflictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conflict_id: UUID
    case_id: UUID
    conflict_type: str
    severity: ConflictSeverity
    title: str
    explanation: str
    event_ids: list[str]
    evidence_refs: list[str]
    details: dict[str, Any] | None
    created_at: datetime


class AnomaliesListResponse(BaseModel):
    case_id: UUID
    anomaly_count: int
    anomalies: list[AnomalyResponse]


class ConflictsListResponse(BaseModel):
    case_id: UUID
    conflict_count: int
    conflicts: list[ConflictResponse]
