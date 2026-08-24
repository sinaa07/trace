from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.events.extractor import EventExtractor
from app.core.processing.registry import ProcessingProfileRegistry
from app.core.temporal.engine import TemporalEngine
from app.models import Event, EvidenceArtifact
from app.services.audit import AuditService
from app.services.storage.repositories.case_repo import CaseRepository
from app.services.storage.repositories.event_repo import EventRepository
from app.services.storage.repositories.evidence_repo import EvidenceRepository


class EventService:
    def __init__(
        self,
        db: Session,
        *,
        profile_registry: ProcessingProfileRegistry | None = None,
        extractor: EventExtractor | None = None,
        temporal_engine: TemporalEngine | None = None,
    ) -> None:
        self.db = db
        self.case_repo = CaseRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.event_repo = EventRepository(db)
        self.audit = AuditService(db)
        self.profile_registry = profile_registry or ProcessingProfileRegistry()
        self.extractor = extractor or EventExtractor()
        self.temporal_engine = temporal_engine or TemporalEngine()

    def extract_for_artifact(
        self,
        artifact: EvidenceArtifact,
        *,
        actor: str = "system",
        rebuild_timeline: bool = True,
    ) -> int:
        if not artifact.profile_id:
            profile = self.profile_registry.get_default_for_source_type(
                artifact.source_type
            )
        else:
            profile = self.profile_registry.get(artifact.profile_id)
            if profile is None:
                profile = self.profile_registry.get_default_for_source_type(
                    artifact.source_type
                )

        case = self.case_repo.get(artifact.case_id)
        records = self.evidence_repo.list_records_for_evidence(
            artifact.evidence_id, valid_only=True
        )

        extraction = self.extractor.extract_from_records(
            records,
            profile,
            case_location=case.location if case else None,
        )

        self.event_repo.delete_for_evidence(artifact.evidence_id)

        db_events: list[Event] = []
        for draft in extraction.events:
            evidence_refs = [str(artifact.evidence_id)]
            db_events.append(
                Event(
                    case_id=artifact.case_id,
                    evidence_id=draft.evidence_id,
                    record_id=draft.record_id,
                    event_type=draft.event_type,
                    raw_timestamp=draft.raw_timestamp,
                    corrected_timestamp=draft.raw_timestamp,
                    temporal_confidence=draft.temporal_confidence,
                    source_id=draft.source_id,
                    entity_id=draft.entity_id,
                    location=draft.location,
                    attributes=draft.attributes,
                    evidence_refs=evidence_refs,
                )
            )

        if db_events:
            self.event_repo.bulk_create(db_events)

        self.audit.log(
            case_id=artifact.case_id,
            entity_type="evidence_artifact",
            entity_id=artifact.evidence_id,
            action="events.extracted",
            payload={
                "profile_id": profile.id,
                "event_count": len(db_events),
                "skipped_records": extraction.skipped_records,
            },
            actor=actor,
        )
        self.db.commit()

        if rebuild_timeline:
            self.rebuild_case_timeline(artifact.case_id, actor=actor)

        return len(db_events)

    def rebuild_case_timeline(
        self, case_id: uuid.UUID, *, actor: str = "system"
    ) -> int:
        case = self.case_repo.get(case_id)
        if not case:
            raise ValueError(f"Case not found: {case_id}")

        events = self.event_repo.list_for_case(case_id)
        if not events:
            return 0

        from app.core.events.extractor import EventDraft

        drafts = [
            EventDraft(
                event_type=e.event_type,
                raw_timestamp=e.raw_timestamp,
                source_id=e.source_id,
                entity_id=e.entity_id,
                location=e.location,
                attributes=e.attributes or {},
                evidence_id=e.evidence_id,
                record_id=e.record_id,
                temporal_confidence=e.temporal_confidence,
            )
            for e in events
        ]

        artifacts = self.evidence_repo.list_artifacts_for_case(case_id)
        evidence_metadata = {
            str(a.evidence_id): dict(a.source_metadata or {}) for a in artifacts
        }

        timeline = self.temporal_engine.reconstruct(
            drafts,
            incident_time=case.incident_time,
            evidence_metadata=evidence_metadata,
        )

        corrected_by_key: dict[tuple[uuid.UUID, str], tuple] = {}
        for idx, corrected in enumerate(timeline.events):
            key = (corrected.draft.record_id, corrected.draft.event_type)
            corrected_by_key[key] = (
                corrected.corrected_timestamp,
                corrected.clock_offset_seconds,
                corrected.temporal_confidence,
                idx,
            )

        for event in events:
            update = corrected_by_key.get((event.record_id, event.event_type))
            if update:
                event.corrected_timestamp = update[0]
                event.clock_offset_seconds = update[1]
                event.temporal_confidence = update[2]
                event.timeline_index = update[3]

        self.event_repo.update_timeline_fields(events)
        self.audit.log(
            case_id=case_id,
            entity_type="case",
            entity_id=case_id,
            action="timeline.rebuilt",
            payload={"event_count": len(events)},
            actor=actor,
        )
        self.db.commit()
        return len(events)

    def get_case_events(
        self,
        case_id: uuid.UUID,
        *,
        event_type: str | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        return self.event_repo.list_for_case(
            case_id, event_type=event_type, limit=limit
        )

    def get_case_timeline(self, case_id: uuid.UUID) -> list[Event]:
        return self.event_repo.list_for_case(case_id)
