"""Phase 4 causal graph + Phase 5 gaps/audit API routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.graph import (
    AuditListResponse,
    CaseGraphResponse,
    EvidenceGapsResponse,
    GraphPathResponse,
)
from app.services.graph_service import GraphService

router = APIRouter(prefix="/cases", tags=["graph"])


def get_graph_service(db: Session = Depends(get_db)) -> GraphService:
    return GraphService(db)


@router.get("/{case_id}/graph", response_model=CaseGraphResponse)
def get_case_graph(
    case_id: uuid.UUID,
    service: Annotated[GraphService, Depends(get_graph_service)],
) -> CaseGraphResponse:
    graph = service.get_graph(case_id)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    return graph


@router.post("/{case_id}/graph/rebuild", response_model=CaseGraphResponse)
def rebuild_case_graph(
    case_id: uuid.UUID,
    service: Annotated[GraphService, Depends(get_graph_service)],
) -> CaseGraphResponse:
    graph = service.build_and_persist(case_id)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    service.rescore_findings_with_causal_support(case_id)
    service.db.commit()
    refreshed = service.get_graph(case_id)
    assert refreshed is not None
    return refreshed


@router.get("/{case_id}/graph/path", response_model=GraphPathResponse)
def trace_graph_path(
    case_id: uuid.UUID,
    service: Annotated[GraphService, Depends(get_graph_service)],
    from_id: str = Query(..., alias="from"),
    to_id: str = Query(..., alias="to"),
) -> GraphPathResponse:
    result = service.find_path(case_id, from_id=from_id, to_id=to_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    return result


@router.get("/{case_id}/gaps", response_model=EvidenceGapsResponse)
def get_case_evidence_gaps(
    case_id: uuid.UUID,
    service: Annotated[GraphService, Depends(get_graph_service)],
) -> EvidenceGapsResponse:
    gaps = service.get_evidence_gaps(case_id)
    if gaps is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    return gaps


@router.get("/{case_id}/audit", response_model=AuditListResponse)
def list_case_audit(
    case_id: uuid.UUID,
    service: Annotated[GraphService, Depends(get_graph_service)],
) -> AuditListResponse:
    audit = service.list_audit(case_id)
    if audit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    return audit
