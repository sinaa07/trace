"""Run Phase 3 investigation agents and persist ranked findings."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.agents.graph import InvestigationOrchestrator
from app.core.config import settings
from app.models.enums import CaseStatus
from app.models.finding import HypothesisFinding
from app.schemas.investigation import (
    HypothesisFindingResponse,
    InvestigationRunResponse,
    RankedHypothesis,
    RankedHypothesesResponse,
)
from app.services.audit import AuditService
from app.services.storage.repositories.case_repo import CaseRepository
from app.services.storage.repositories.finding_repo import FindingRepository


class InvestigationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.cases = CaseRepository(db)
        self.findings = FindingRepository(db)
        self.audit = AuditService(db)

    def run_investigation(
        self,
        case_id: uuid.UUID,
        *,
        actor: str = "system",
        replace_existing: bool = True,
        llm_provider: str | None = None,
    ) -> InvestigationRunResponse | None:
        case = self.cases.get(case_id)
        if case is None:
            return None

        if replace_existing:
            self.findings.delete_for_case(case_id)

        orchestrator = InvestigationOrchestrator(
            self.db,
            llm_provider=llm_provider or settings.llm_provider,
            max_iterations=settings.investigation_max_iterations,
        )
        state = orchestrator.run(case_id)

        persisted: list[HypothesisFindingResponse] = []
        ranked: list[RankedHypothesis] = []

        for result in state.findings:
            row = HypothesisFinding(
                case_id=case_id,
                agent_id=result.agent_id,
                domain=result.finding.domain,
                hypothesis=result.finding.hypothesis,
                reasoning=result.finding.reasoning,
                supporting_evidence=result.finding.supporting_evidence,
                contradicting_evidence=result.finding.contradicting_evidence,
                relevant_events=result.finding.relevant_events,
                missing_evidence=result.finding.missing_evidence,
                assumptions=result.finding.assumptions,
                reasoning_summary=result.finding.reasoning_summary,
                confidence=result.finding.confidence,
                uncertainty=result.finding.uncertainty,
                domain_features=result.finding.domain_features,
                rank_score=result.weighted_score,
                rank_dimensions=(
                    result.dimensions.model_dump() if result.dimensions else None
                ),
                run_id=state.run_id,
            )
            self.findings.create(row)
            response = self._to_response(row)
            persisted.append(response)
            if result.dimensions is not None:
                ranked.append(
                    RankedHypothesis(
                        finding=response,
                        dimensions=result.dimensions,
                        weighted_score=result.weighted_score,
                    )
                )

        if case.status in {CaseStatus.OPEN, CaseStatus.READY, CaseStatus.INGESTING}:
            case.status = CaseStatus.INVESTIGATING

        self.audit.log(
            case_id=case_id,
            entity_type="case",
            entity_id=case_id,
            action="investigation.completed",
            actor=actor,
            payload={
                "run_id": str(state.run_id),
                "finding_count": len(persisted),
                "provider": state.provider,
                "meta_summary": state.meta_summary[:1000],
            },
        )
        self.db.commit()

        ranked.sort(key=lambda r: r.weighted_score, reverse=True)
        return InvestigationRunResponse(
            case_id=case_id,
            run_id=state.run_id,
            generated_at=datetime.now(timezone.utc),
            provider=state.provider,
            meta_summary=state.meta_summary,
            findings=persisted,
            ranked=ranked,
        )

    def list_findings(self, case_id: uuid.UUID) -> list[HypothesisFindingResponse] | None:
        if self.cases.get(case_id) is None:
            return None
        return [self._to_response(row) for row in self.findings.list_for_case(case_id)]

    def list_ranked_hypotheses(
        self, case_id: uuid.UUID
    ) -> RankedHypothesesResponse | None:
        if self.cases.get(case_id) is None:
            return None
        from app.schemas.investigation import RankingDimensionScores

        rows = self.findings.list_for_case(case_id)
        ranked: list[RankedHypothesis] = []
        for row in rows:
            finding = self._to_response(row)
            dims_data = row.rank_dimensions if isinstance(row.rank_dimensions, dict) else {}
            dims = RankingDimensionScores(
                evidence_support=float(dims_data.get("evidence_support", 0.0)),
                temporal_consistency=float(dims_data.get("temporal_consistency", 0.0)),
                source_reliability=float(dims_data.get("source_reliability", 0.0)),
                causal_support=float(dims_data.get("causal_support", 0.0)),
                evidence_completeness=float(dims_data.get("evidence_completeness", 0.0)),
                contradiction_penalty=float(dims_data.get("contradiction_penalty", 0.0)),
            )
            ranked.append(
                RankedHypothesis(
                    finding=finding,
                    dimensions=dims,
                    weighted_score=float(row.rank_score or 0.0),
                )
            )
        ranked.sort(key=lambda r: r.weighted_score, reverse=True)
        return RankedHypothesesResponse(
            case_id=case_id,
            hypotheses=ranked,
            total=len(ranked),
        )

    @staticmethod
    def _to_response(row: HypothesisFinding) -> HypothesisFindingResponse:
        return HypothesisFindingResponse(
            finding_id=row.finding_id,
            case_id=row.case_id,
            agent_id=row.agent_id,
            domain=row.domain,
            hypothesis=row.hypothesis,
            reasoning=row.reasoning,
            supporting_evidence=list(row.supporting_evidence or []),
            contradicting_evidence=list(row.contradicting_evidence or []),
            relevant_events=list(row.relevant_events or []),
            missing_evidence=list(row.missing_evidence or []),
            assumptions=list(row.assumptions or []),
            reasoning_summary=row.reasoning_summary or "",
            confidence=row.confidence,
            uncertainty=row.uncertainty,
            domain_features=row.domain_features,
            rank_score=row.rank_score,
            created_at=row.created_at,
        )
