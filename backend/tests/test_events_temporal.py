from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.events.extractor import EventExtractor
from app.core.processing.registry import ProcessingProfileRegistry
from app.core.temporal.engine import TemporalEngine
from app.models import EvidenceRecord


def _record(normalized: dict, *, valid: bool = True) -> EvidenceRecord:
    return EvidenceRecord(
        record_id=uuid4(),
        evidence_id=uuid4(),
        case_id=uuid4(),
        record_index=0,
        raw_data=normalized,
        normalized_data=normalized,
        is_valid=valid,
    )


def test_signal_log_event_extraction():
    registry = ProcessingProfileRegistry()
    profile = registry.get("signal_log_v1")
    extractor = EventExtractor()

    records = [
        _record(
            {
                "timestamp": "2024-03-15T08:12:04+00:00",
                "signal_id": "SIGNAL-S42",
                "state": "RED",
                "train_id": "TRAIN-102",
            }
        )
    ]
    result = extractor.extract_from_records(records, profile)
    assert len(result.events) == 1
    assert result.events[0].event_type == "SIGNAL_STATE_CHANGE"
    assert result.events[0].source_id == "SIGNAL-S42"
    assert result.events[0].entity_id == "TRAIN-102"


def test_train_telemetry_emits_multiple_event_types():
    registry = ProcessingProfileRegistry()
    profile = registry.get("train_telemetry_v1")
    extractor = EventExtractor()

    records = [
        _record(
            {
                "timestamp": "2024-03-15T08:12:05+00:00",
                "train_id": "TRAIN-102",
                "speed": 65.0,
                "brake_status": "applied",
            }
        )
    ]
    result = extractor.extract_from_records(records, profile)
    types = {e.event_type for e in result.events}
    assert "SPEED_SAMPLE" in types
    assert "BRAKE_STATUS" in types


def test_invalid_records_skipped():
    registry = ProcessingProfileRegistry()
    profile = registry.get("signal_log_v1")
    extractor = EventExtractor()
    result = extractor.extract_from_records(
        [_record({"timestamp": "x", "signal_id": "S42", "state": "RED"}, valid=False)],
        profile,
    )
    assert result.events == []
    assert result.skipped_records == 1


def test_temporal_engine_orders_events():
    engine = TemporalEngine()
    from app.core.events.extractor import EventDraft

    eid = uuid4()
    drafts = [
        EventDraft(
            event_type="A",
            raw_timestamp=datetime(2024, 3, 15, 8, 12, 10, tzinfo=timezone.utc),
            source_id=None,
            entity_id=None,
            location=None,
            attributes={},
            evidence_id=eid,
            record_id=uuid4(),
        ),
        EventDraft(
            event_type="B",
            raw_timestamp=datetime(2024, 3, 15, 8, 12, 4, tzinfo=timezone.utc),
            source_id=None,
            entity_id=None,
            location=None,
            attributes={},
            evidence_id=eid,
            record_id=uuid4(),
        ),
    ]
    result = engine.reconstruct(drafts)
    times = [e.corrected_timestamp for e in result.events if e.corrected_timestamp]
    assert times == sorted(times)


def test_temporal_anchor_offset():
    engine = TemporalEngine()
    from app.core.events.extractor import EventDraft

    eid = uuid4()
    incident = datetime(2024, 3, 15, 8, 12, 0, tzinfo=timezone.utc)
    drafts = [
        EventDraft(
            event_type="SIGNAL_STATE_CHANGE",
            raw_timestamp=datetime(2024, 3, 15, 8, 11, 50, tzinfo=timezone.utc),
            source_id="S42",
            entity_id=None,
            location=None,
            attributes={},
            evidence_id=eid,
            record_id=uuid4(),
        )
    ]
    result = engine.reconstruct(drafts, incident_time=incident)
    assert result.offsets_by_evidence[str(eid)] == pytest.approx(10.0, abs=0.1)
