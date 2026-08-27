"""Investigation / hypothesis schemas (Phase 3 contracts)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DomainFeatureResultModel(BaseModel):
    domain: str
    score: float | None = None
    summary: str
    features: dict[str, Any] = Field(default_factory=dict)
    inputs_used: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DomainFeaturesResponse(BaseModel):
    case_id: UUID
    generated_at: datetime
    domains: list[DomainFeatureResultModel]
    notes: list[str] = Field(default_factory=list)


class HypothesisFindingCreate(BaseModel):
    """Structured agent output contract (LLM or rule-based)."""

    domain: str
    hypothesis: str
    reasoning: str
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    relevant_events: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    uncertainty: str | None = None
    domain_features: dict[str, Any] | None = None


class HypothesisFindingResponse(HypothesisFindingCreate):
    finding_id: UUID
    case_id: UUID
    agent_id: str
    rank_score: float | None = None
    created_at: datetime


class RankingDimensionScores(BaseModel):
    evidence_support: float = Field(ge=0.0, le=1.0, default=0.0)
    temporal_consistency: float = Field(ge=0.0, le=1.0, default=0.0)
    source_reliability: float = Field(ge=0.0, le=1.0, default=0.0)
    causal_support: float = Field(ge=0.0, le=1.0, default=0.0)
    evidence_completeness: float = Field(ge=0.0, le=1.0, default=0.0)
    contradiction_penalty: float = Field(ge=0.0, le=1.0, default=0.0)


class RankedHypothesis(BaseModel):
    finding: HypothesisFindingResponse
    dimensions: RankingDimensionScores
    weighted_score: float


class InvestigationRunRequest(BaseModel):
    actor: str = "investigator"
    replace_existing: bool = True
    llm_provider: str | None = None


class InvestigationRunResponse(BaseModel):
    case_id: UUID
    run_id: UUID
    generated_at: datetime
    provider: str
    meta_summary: str
    findings: list[HypothesisFindingResponse]
    ranked: list[RankedHypothesis]


class FindingsListResponse(BaseModel):
    case_id: UUID
    findings: list[HypothesisFindingResponse]
    total: int


class RankedHypothesesResponse(BaseModel):
    case_id: UUID
    hypotheses: list[RankedHypothesis]
    total: int
