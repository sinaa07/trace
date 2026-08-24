import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import EvidenceArtifactResponse
from app.services.ingestion import IngestionOrchestrator

router = APIRouter(prefix="/evidence", tags=["evidence"])


def get_ingestion_service(db: Session = Depends(get_db)) -> IngestionOrchestrator:
    return IngestionOrchestrator(db)


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
