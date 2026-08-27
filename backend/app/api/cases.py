import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.enums import SourceType
from app.schemas import (
    CaseCreate,
    CaseListResponse,
    CaseResponse,
    CaseUpdate,
    EvidenceArtifactResponse,
    EvidenceListResponse,
    EvidenceRecordsListResponse,
)
from app.services.case_service import CaseService
from app.services.evidence_service import EvidenceService
from app.services.ingestion import DuplicateEvidenceError, IngestionOrchestrator

router = APIRouter(prefix="/cases", tags=["cases"])


def get_case_service(db: Session = Depends(get_db)) -> CaseService:
    return CaseService(db)


def get_ingestion_service(db: Session = Depends(get_db)) -> IngestionOrchestrator:
    return IngestionOrchestrator(db)


def get_evidence_service(db: Session = Depends(get_db)) -> EvidenceService:
    return EvidenceService(db)


def _case_response(case, evidence_count: int = 0) -> CaseResponse:
    response = CaseResponse.model_validate(case)
    response.evidence_count = evidence_count
    metadata = case.metadata_ or {}
    response.created_by = metadata.get("created_by")
    return response


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    service: Annotated[CaseService, Depends(get_case_service)],
) -> CaseResponse:
    case = service.create_case(payload)
    return _case_response(case)


@router.get("", response_model=CaseListResponse)
def list_cases(
    service: Annotated[CaseService, Depends(get_case_service)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CaseListResponse:
    try:
        items, total = service.list_cases(limit=limit, offset=offset)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "CASE_LIST_FAILED",
                    "message": f"Failed to list cases: {exc}",
                }
            },
        ) from exc
    return CaseListResponse(
        items=[_case_response(case, count) for case, count in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: uuid.UUID,
    service: Annotated[CaseService, Depends(get_case_service)],
) -> CaseResponse:
    case, count = service.get_case_with_count(case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    return _case_response(case, count)


@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(
    case_id: uuid.UUID,
    payload: CaseUpdate,
    service: Annotated[CaseService, Depends(get_case_service)],
) -> CaseResponse:
    case = service.update_case(case_id, payload)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    _, count = service.get_case_with_count(case_id)
    return _case_response(case, count)


@router.get("/{case_id}/evidence", response_model=EvidenceListResponse)
def list_case_evidence(
    case_id: uuid.UUID,
    case_service: Annotated[CaseService, Depends(get_case_service)],
    ingestion: Annotated[IngestionOrchestrator, Depends(get_ingestion_service)],
) -> EvidenceListResponse:
    case, _ = case_service.get_case_with_count(case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )

    artifacts = ingestion.evidence_repo.list_artifacts_for_case(case_id)
    items: list[EvidenceArtifactResponse] = []
    for artifact in artifacts:
        _, total, invalid, warnings = ingestion.get_artifact_summary(artifact.evidence_id)
        response = EvidenceArtifactResponse.model_validate(artifact)
        response.record_count = total
        response.invalid_record_count = invalid
        response.warning_count = warnings
        items.append(response)

    return EvidenceListResponse(case_id=case_id, items=items, total=len(items))


@router.get("/{case_id}/records", response_model=EvidenceRecordsListResponse)
def list_case_records(
    case_id: uuid.UUID,
    case_service: Annotated[CaseService, Depends(get_case_service)],
    evidence_service: Annotated[EvidenceService, Depends(get_evidence_service)],
    evidence_id: Annotated[uuid.UUID | None, Query()] = None,
    source_type: Annotated[SourceType | None, Query()] = None,
    is_valid: Annotated[bool | None, Query()] = None,
    has_warnings: Annotated[bool | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EvidenceRecordsListResponse:
    case, _ = case_service.get_case_with_count(case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    try:
        items, total = evidence_service.search_case_records(
            case_id,
            evidence_id=evidence_id,
            source_type=source_type,
            is_valid=is_valid,
            has_warnings=has_warnings,
            q=q,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "RECORD_SEARCH_FAILED",
                    "message": f"Failed to search evidence records: {exc}",
                }
            },
        ) from exc

    return EvidenceRecordsListResponse(
        case_id=case_id,
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        filters={
            "evidence_id": str(evidence_id) if evidence_id else None,
            "source_type": source_type.value if source_type else None,
            "is_valid": is_valid,
            "has_warnings": has_warnings,
            "q": q,
        },
    )


@router.post(
    "/{case_id}/evidence",
    response_model=EvidenceArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_evidence(
    case_id: uuid.UUID,
    ingestion: Annotated[IngestionOrchestrator, Depends(get_ingestion_service)],
    file: UploadFile = File(...),
    source_type: SourceType = Form(...),
    source_metadata: str | None = Form(default=None),
    actor: str = Form(default="system"),
) -> EvidenceArtifactResponse:
    content = await file.read()
    metadata = json.loads(source_metadata) if source_metadata else None
    if metadata is None:
        metadata = {}
    if actor and actor != "system":
        metadata.setdefault("operator", actor)

    try:
        artifact = await ingestion.ingest(
            case_id=case_id,
            filename=file.filename or "upload.bin",
            content=content,
            source_type=source_type,
            source_metadata=metadata,
            mime=file.content_type,
            actor=actor.strip() or "system",
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": message}},
            ) from exc
        if "maximum upload size" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={"error": {"code": "FILE_TOO_LARGE", "message": message}},
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": message}},
        ) from exc
    except DuplicateEvidenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "DUPLICATE_HASH",
                    "message": str(exc),
                    "details": {"sha256": exc.sha256},
                }
            },
        ) from exc
    except Exception as exc:
        from app.core.parsers.base import UnsupportedFormatError

        if isinstance(exc, UnsupportedFormatError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "code": "UNSUPPORTED_FORMAT",
                        "message": str(exc),
                    }
                },
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INGESTION_FAILED", "message": str(exc)}},
        ) from exc

    _, total, invalid, warnings = ingestion.get_artifact_summary(artifact.evidence_id)
    response = EvidenceArtifactResponse.model_validate(artifact)
    response.record_count = total
    response.invalid_record_count = invalid
    response.warning_count = warnings
    return response
