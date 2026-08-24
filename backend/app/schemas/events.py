from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: UUID
    case_id: UUID
    evidence_id: UUID
    record_id: UUID
    event_type: str
    raw_timestamp: datetime | None
    corrected_timestamp: datetime | None
    temporal_confidence: float
    clock_offset_seconds: float | None
    source_id: str | None
    entity_id: str | None
    location: dict[str, Any] | None
    attributes: dict[str, Any]
    evidence_refs: list[str]
    timeline_index: int | None
    created_at: datetime


class TimelineResponse(BaseModel):
    case_id: UUID
    event_count: int
    events: list[EventResponse]
    rebuilt_at: datetime | None = None


class EventsListResponse(BaseModel):
    case_id: UUID
    event_count: int
    events: list[EventResponse]
    filters: dict[str, Any] = Field(default_factory=dict)
