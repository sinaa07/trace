"""Quality analysis API: anomalies and evidence conflicts."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.quality import (
    AnomaliesListResponse,
    AnomalyResponse,
    ConflictResponse,
    ConflictsListResponse,
)
from app.services.quality_service import QualityAnalysisService
from app.services.storage.repositories.case_repo import CaseRepository

router = APIRouter(prefix="/cases", tags=["quality"])


def get_quality_service(db: Session = Depends(get_db)) -> QualityAnalysisService:
    return QualityAnalysisService(db)


def get_case_repo(db: Session = Depends(get_db)) -> CaseRepository:
    return CaseRepository(db)


@router.get("/{case_id}/anomalies", response_model=AnomaliesListResponse)
def list_case_anomalies(
    case_id: uuid.UUID,
    quality: Annotated[QualityAnalysisService, Depends(get_quality_service)],
    case_repo: Annotated[CaseRepository, Depends(get_case_repo)],
) -> AnomaliesListResponse:
    if not case_repo.get(case_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    anomalies = quality.get_anomalies(case_id)
    return AnomaliesListResponse(
        case_id=case_id,
        anomaly_count=len(anomalies),
        anomalies=[AnomalyResponse.model_validate(a) for a in anomalies],
    )


@router.get("/{case_id}/conflicts", response_model=ConflictsListResponse)
def list_case_conflicts(
    case_id: uuid.UUID,
    quality: Annotated[QualityAnalysisService, Depends(get_quality_service)],
    case_repo: Annotated[CaseRepository, Depends(get_case_repo)],
) -> ConflictsListResponse:
    if not case_repo.get(case_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    conflicts = quality.get_conflicts(case_id)
    return ConflictsListResponse(
        case_id=case_id,
        conflict_count=len(conflicts),
        conflicts=[ConflictResponse.model_validate(c) for c in conflicts],
    )
