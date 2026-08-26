import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.services.storage.repositories.audit_repo import AuditRepository

class AuditService:
    def __init__(self, db: Session) -> None:
        self.repo = AuditRepository(db)

    def log(
        self,
        case_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        action: str,
        payload: dict[str, Any] | None = None,
        actor: str = "system",
    ) -> AuditEvent:
        event = AuditEvent(
            case_id=case_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            payload=payload,
        )
        return self.repo.create(event)
