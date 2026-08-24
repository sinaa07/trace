import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.events import EventResponse, EventsListResponse, TimelineResponse
from app.services.event_service import EventService
from app.services.storage.repositories.case_repo import CaseRepository

router = APIRouter(prefix="/cases", tags=["timeline"])


def get_event_service(db: Session = Depends(get_db)) -> EventService:
    return EventService(db)


def get_case_repo(db: Session = Depends(get_db)) -> CaseRepository:
    return CaseRepository(db)


@router.get("/{case_id}/events", response_model=EventsListResponse)
def list_case_events(
    case_id: uuid.UUID,
    event_service: Annotated[EventService, Depends(get_event_service)],
    case_repo: Annotated[CaseRepository, Depends(get_case_repo)],
    event_type: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=1000),
) -> EventsListResponse:
    if not case_repo.get(case_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    events = event_service.get_case_events(
        case_id, event_type=event_type, limit=limit
    )
    return EventsListResponse(
        case_id=case_id,
        event_count=len(events),
        events=[EventResponse.model_validate(e) for e in events],
        filters={"event_type": event_type, "limit": limit},
    )


@router.get("/{case_id}/timeline", response_model=TimelineResponse)
def get_case_timeline(
    case_id: uuid.UUID,
    event_service: Annotated[EventService, Depends(get_event_service)],
    case_repo: Annotated[CaseRepository, Depends(get_case_repo)],
) -> TimelineResponse:
    if not case_repo.get(case_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    events = event_service.get_case_timeline(case_id)
    return TimelineResponse(
        case_id=case_id,
        event_count=len(events),
        events=[EventResponse.model_validate(e) for e in events],
        rebuilt_at=datetime.now(timezone.utc) if events else None,
    )


@router.post("/{case_id}/timeline/rebuild", response_model=TimelineResponse)
def rebuild_case_timeline(
    case_id: uuid.UUID,
    event_service: Annotated[EventService, Depends(get_event_service)],
    case_repo: Annotated[CaseRepository, Depends(get_case_repo)],
) -> TimelineResponse:
    if not case_repo.get(case_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Case not found"}},
        )
    try:
        event_service.rebuild_case_timeline(case_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc)}},
        ) from exc

    events = event_service.get_case_timeline(case_id)
    return TimelineResponse(
        case_id=case_id,
        event_count=len(events),
        events=[EventResponse.model_validate(e) for e in events],
        rebuilt_at=datetime.now(timezone.utc),
    )
