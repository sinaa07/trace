"""Extract normalized Events from cleaned EvidenceRecords using ProcessingProfile rules."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.processing.profile import ProcessingProfile
from app.models import EvidenceRecord


@dataclass
class EventDraft:
    event_type: str
    raw_timestamp: datetime | None
    source_id: str | None
    entity_id: str | None
    location: dict[str, Any] | None
    attributes: dict[str, Any]
    evidence_id: uuid.UUID
    record_id: uuid.UUID
    temporal_confidence: float = 1.0


@dataclass
class ExtractionResult:
    events: list[EventDraft] = field(default_factory=list)
    skipped_records: int = 0
    warnings: list[str] = field(default_factory=list)


class EventExtractor:
    def extract_from_records(
        self,
        records: list[EvidenceRecord],
        profile: ProcessingProfile,
        *,
        case_location: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        result = ExtractionResult()
        if not profile.event_rules:
            result.warnings.append(f"No event_rules defined for profile {profile.id}")
            return result

        for record in records:
            if not record.is_valid:
                result.skipped_records += 1
                continue
            normalized = record.normalized_data or {}
            emitted = False
            for rule in profile.event_rules:
                if not self._rule_matches(normalized, rule):
                    continue
                draft = self._build_draft(
                    rule,
                    normalized,
                    record,
                    case_location=case_location,
                )
                if draft:
                    result.events.append(draft)
                    emitted = True
            if not emitted:
                result.skipped_records += 1

        return result

    @staticmethod
    def _rule_matches(normalized: dict[str, Any], rule) -> bool:
        for field_name in rule.required_fields:
            value = normalized.get(field_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                return False
        return True

    @staticmethod
    def _build_draft(
        rule,
        normalized: dict[str, Any],
        record: EvidenceRecord,
        *,
        case_location: dict[str, Any] | None,
    ) -> EventDraft | None:
        raw_ts = EventExtractor._parse_timestamp(normalized.get("timestamp"))
        confidence = 1.0 if raw_ts else 0.5

        attributes: dict[str, Any] = {}
        for attr_key, source_field in rule.attribute_map.items():
            if source_field in normalized and normalized[source_field] is not None:
                attributes[attr_key] = normalized[source_field]

        source_id = (
            str(normalized[rule.source_id_field])
            if rule.source_id_field and normalized.get(rule.source_id_field)
            else None
        )
        entity_id = (
            str(normalized[rule.entity_id_field])
            if rule.entity_id_field and normalized.get(rule.entity_id_field)
            else None
        )

        return EventDraft(
            event_type=rule.emit,
            raw_timestamp=raw_ts,
            source_id=source_id,
            entity_id=entity_id,
            location=case_location,
            attributes=attributes,
            evidence_id=record.evidence_id,
            record_id=record.record_id,
            temporal_confidence=confidence,
        )

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None
