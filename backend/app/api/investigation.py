"""Domain features + investigation agent APIs (Phase 3)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.investigation import (
    DomainFeaturesResponse,
    FindingsListResponse,
    InvestigationRunRequest,
    InvestigationRunResponse,
    RankedHypothesesResponse,
)
from app.services.domain_feature_service import DomainFeatureService
from app.services.investigation_service import InvestigationService

router = APIRouter(prefix="/cases", tags=["investigation"])


def get_domain_feature_service(db: Session = Depends(get_db)) -> DomainFeatureService:
    return DomainFeatureService(db)


def get_investigation_service(db: Session = Depends(get_db)) -> InvestigationService:
    return InvestigationService(db)


@router.get("/{case_id}/domain-features", response_model=DomainFeaturesResponse)
def get_case_domain_features(
    case_id: uuid.UUID,
    service: Annotated[DomainFeatureService, Depends(get_domain_feature_service)],
) -> DomainFeaturesResponse:
    try:
        result = service.compute_for_case(case_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "DOMAIN_FEATURES_FAILED",
                    "message": f"Failed to compute domain features: {exc}",
                }
            },
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    return result


@router.post("/{case_id}/investigate", response_model=InvestigationRunResponse)
def run_case_investigation(
    case_id: uuid.UUID,
    service: Annotated[InvestigationService, Depends(get_investigation_service)],
    body: InvestigationRunRequest | None = None,
) -> InvestigationRunResponse:
    req = body or InvestigationRunRequest()
    try:
        result = service.run_investigation(
            case_id,
            actor=req.actor,
            replace_existing=req.replace_existing,
            llm_provider=req.llm_provider,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INVESTIGATION_FAILED",
                    "message": f"Investigation failed: {exc}",
                }
            },
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    return result


@router.get("/{case_id}/findings", response_model=FindingsListResponse)
def list_case_findings(
    case_id: uuid.UUID,
    service: Annotated[InvestigationService, Depends(get_investigation_service)],
) -> FindingsListResponse:
    findings = service.list_findings(case_id)
    if findings is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    return FindingsListResponse(
        case_id=case_id, findings=findings, total=len(findings)
    )


@router.get("/{case_id}/hypotheses", response_model=RankedHypothesesResponse)
def list_case_hypotheses(
    case_id: uuid.UUID,
    service: Annotated[InvestigationService, Depends(get_investigation_service)],
) -> RankedHypothesesResponse:
    result = service.list_ranked_hypotheses(case_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    return result
