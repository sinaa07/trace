"""Evidence-weighted hypothesis ranking (deterministic; not Bayesian)."""

from __future__ import annotations

from app.schemas.investigation import (
    HypothesisFindingCreate,
    RankingDimensionScores,
)


DEFAULT_WEIGHTS = {
    "evidence_support": 0.30,
    "temporal_consistency": 0.20,
    "source_reliability": 0.15,
    "causal_support": 0.10,
    "evidence_completeness": 0.15,
    "contradiction_penalty": 0.10,
}


def score_hypothesis(
    finding: HypothesisFindingCreate,
    *,
    source_reliability: float = 0.7,
    temporal_consistency: float = 0.7,
    causal_support: float = 0.0,
    weights: dict[str, float] | None = None,
) -> tuple[RankingDimensionScores, float]:
    """Transparent weighted score for MVP ranking.

    Agent `confidence` is an input signal only — it is not treated as a probability.
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    support_n = len(finding.supporting_evidence)
    contradict_n = len(finding.contradicting_evidence)
    missing_n = len(finding.missing_evidence)

    evidence_support = min(support_n / 3.0, 1.0) * 0.7 + min(max(finding.confidence, 0.0), 1.0) * 0.3
    contradiction_penalty = min(contradict_n / 2.0, 1.0)
    completeness = max(0.0, 1.0 - min(missing_n / 3.0, 1.0))

    dimensions = RankingDimensionScores(
        evidence_support=round(evidence_support, 4),
        temporal_consistency=round(min(max(temporal_consistency, 0.0), 1.0), 4),
        source_reliability=round(min(max(source_reliability, 0.0), 1.0), 4),
        causal_support=round(min(max(causal_support, 0.0), 1.0), 4),
        evidence_completeness=round(completeness, 4),
        contradiction_penalty=round(contradiction_penalty, 4),
    )

    weighted = (
        w["evidence_support"] * dimensions.evidence_support
        + w["temporal_consistency"] * dimensions.temporal_consistency
        + w["source_reliability"] * dimensions.source_reliability
        + w["causal_support"] * dimensions.causal_support
        + w["evidence_completeness"] * dimensions.evidence_completeness
        - w["contradiction_penalty"] * dimensions.contradiction_penalty
    )
    return dimensions, round(max(0.0, min(weighted, 1.0)), 4)
