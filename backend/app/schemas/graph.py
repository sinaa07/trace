"""Pydantic schemas for Phase 4 causal graph API."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class GraphNodeModel(BaseModel):
    id: str
    label: str
    node_type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdgeModel(BaseModel):
    source: str
    target: str
    edge_type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class CaseGraphResponse(BaseModel):
    case_id: UUID
    nodes: list[GraphNodeModel]
    edges: list[GraphEdgeModel]
    node_count: int
    edge_count: int
    built_from: str | None = None


class GraphPathResponse(BaseModel):
    case_id: UUID
    from_id: str
    to_id: str
    found: bool
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class EvidenceGapsResponse(BaseModel):
    case_id: UUID
    missing_source_types: list[str] = Field(default_factory=list)
    missing_domain_inputs: list[str] = Field(default_factory=list)
    needs_review_or_failed: list[dict[str, Any]] = Field(default_factory=list)
    external_weather_available: bool = False


class AuditEventResponse(BaseModel):
    audit_id: UUID
    case_id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    actor: str
    payload: dict[str, Any] | None = None
    created_at: str


class AuditListResponse(BaseModel):
    case_id: UUID
    events: list[AuditEventResponse]
    total: int
