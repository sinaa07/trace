import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import (
    EvidenceArtifactResponse,
    EvidenceRecordResponse,
    EvidenceRecordsListResponse,
)
from app.services.evidence_service import EvidenceDeleteForbiddenError, EvidenceService
from app.services.ingestion import IngestionOrchestrator

router = APIRouter(prefix="/evidence", tags=["evidence"])


def get_ingestion_service(db: Session = Depends(get_db)) -> IngestionOrchestrator:
    return IngestionOrchestrator(db)


def get_evidence_service(db: Session = Depends(get_db)) -> EvidenceService:
    return EvidenceService(db)


@router.get("/records/{record_id}", response_model=EvidenceRecordResponse)
def get_evidence_record(
    record_id: uuid.UUID,
    service: Annotated[EvidenceService, Depends(get_evidence_service)],
) -> EvidenceRecordResponse:
    """Static path registered before /{evidence_id} to avoid UUID capture."""
    try:
        record = service.get_record(record_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "RECORD_FETCH_FAILED",
                    "message": f"Failed to fetch evidence record: {exc}",
                }
            },
        ) from exc
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Evidence record not found",
                }
            },
        )
    return record


@router.get("/{evidence_id}", response_model=EvidenceArtifactResponse)
def get_evidence(
    evidence_id: uuid.UUID,
    ingestion: Annotated[IngestionOrchestrator, Depends(get_ingestion_service)],
) -> EvidenceArtifactResponse:
    artifact, total, invalid, warnings = ingestion.get_artifact_summary(evidence_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Evidence not found"}},
        )
    response = EvidenceArtifactResponse.model_validate(artifact)
    response.record_count = total
    response.invalid_record_count = invalid
    response.warning_count = warnings
    return response


@router.get("/{evidence_id}/records", response_model=EvidenceRecordsListResponse)
def list_evidence_records(
    evidence_id: uuid.UUID,
    service: Annotated[EvidenceService, Depends(get_evidence_service)],
    valid_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EvidenceRecordsListResponse:
    try:
        artifact, items, total = service.list_artifact_records(
            evidence_id, valid_only=valid_only, limit=limit, offset=offset
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "RECORD_LIST_FAILED",
                    "message": f"Failed to list evidence records: {exc}",
                }
            },
        ) from exc
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Evidence not found"}},
        )
    return EvidenceRecordsListResponse(
        case_id=artifact.case_id,
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        filters={"evidence_id": str(evidence_id), "valid_only": valid_only},
    )


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence(
    evidence_id: uuid.UUID,
    actor: Annotated[str, Query(min_length=1, max_length=256)],
    service: Annotated[EvidenceService, Depends(get_evidence_service)],
) -> None:
    try:
        service.delete_evidence(evidence_id, actor.strip())
    except EvidenceDeleteForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": str(exc)}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc)}},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "EVIDENCE_DELETE_FAILED",
                    "message": f"Failed to delete evidence: {exc}",
                }
            },
        ) from exc
