from datetime import datetime, timezone
from uuid import uuid4

import numpy as np
import pytest

from app.core.anomalies.engine import AnomalyRuleEngine
from app.core.conflicts.detector import ConflictDetector
from app.core.temporal.engine import TemporalEngine
from app.core.events.extractor import EventDraft
from app.models import Event


def _event(**kwargs) -> Event:
    defaults = {
        "event_id": uuid4(),
        "case_id": uuid4(),
        "evidence_id": uuid4(),
        "record_id": uuid4(),
        "event_type": "SIGNAL_STATE_CHANGE",
        "raw_timestamp": datetime(2024, 3, 15, 8, 12, 0, tzinfo=timezone.utc),
        "corrected_timestamp": datetime(2024, 3, 15, 8, 12, 0, tzinfo=timezone.utc),
        "temporal_confidence": 1.0,
        "attributes": {"state": "RED"},
        "evidence_refs": [],
    }
    defaults.update(kwargs)
    return Event(**defaults)


def test_affine_drift_from_metadata():
    engine = TemporalEngine()
    eid = uuid4()
    raw = datetime(2024, 3, 15, 8, 0, 0, tzinfo=timezone.utc)
    drafts = [
        EventDraft(
            event_type="A",
            raw_timestamp=raw,
            source_id=None,
            entity_id=None,
            location=None,
            attributes={},
            evidence_id=eid,
            record_id=uuid4(),
        )
    ]
    result = engine.reconstruct(
        drafts,
        evidence_metadata={
            str(eid): {
                "clock_drift_factor": 1.01,
                "clock_offset_seconds": 10.0,
            }
        },
    )
    corrected = result.events[0].corrected_timestamp
    expected_epoch = 1.01 * raw.timestamp() + 10.0
    assert corrected.timestamp() == pytest.approx(expected_epoch, abs=0.01)
    assert result.events[0].clock_drift_factor == pytest.approx(1.01)


def test_affine_fit_from_clock_anchors():
    engine = TemporalEngine()
    eid = uuid4()
    raw1 = datetime(2024, 3, 15, 8, 0, 0, tzinfo=timezone.utc)
    raw2 = datetime(2024, 3, 15, 9, 0, 0, tzinfo=timezone.utc)
    true1 = datetime(2024, 3, 15, 8, 0, 10, tzinfo=timezone.utc)
    true2 = datetime(2024, 3, 15, 9, 0, 20, tzinfo=timezone.utc)

    drafts = [
        EventDraft(
            event_type="A",
            raw_timestamp=raw1,
            source_id=None,
            entity_id=None,
            location=None,
            attributes={},
            evidence_id=eid,
            record_id=uuid4(),
        ),
        EventDraft(
            event_type="B",
            raw_timestamp=raw2,
            source_id=None,
            entity_id=None,
            location=None,
            attributes={},
            evidence_id=eid,
            record_id=uuid4(),
        ),
    ]
    result = engine.reconstruct(
        drafts,
        evidence_metadata={
            str(eid): {
                "clock_anchors": [
                    {"raw": raw1.isoformat(), "true": true1.isoformat()},
                    {"raw": raw2.isoformat(), "true": true2.isoformat()},
                ]
            }
        },
    )
    assert result.events[0].corrected_timestamp == true1
    assert result.events[1].corrected_timestamp == true2


def test_speed_threshold_anomaly():
    engine = AnomalyRuleEngine()
    events = [
        _event(
            event_type="SPEED_SAMPLE",
            entity_id="TRAIN-102",
            attributes={"speed": 130},
        )
    ]
    findings = engine.evaluate(events)
    assert any(f.rule_id == "speed_threshold_exceeded" for f in findings)


def test_signal_state_conflict_detection():
    detector = ConflictDetector(alignment_tolerance_seconds=5.0)
    ts = datetime(2024, 3, 15, 8, 12, 0, tzinfo=timezone.utc)
    events = [
        _event(
            source_id="SIGNAL-S42",
            corrected_timestamp=ts,
            attributes={"state": "RED"},
            evidence_id=uuid4(),
        ),
        _event(
            source_id="SIGNAL-S42",
            corrected_timestamp=ts.replace(second=2),
            attributes={"state": "GREEN"},
            evidence_id=uuid4(),
        ),
    ]
    findings = detector.evaluate(events)
    assert len(findings) == 1
    assert findings[0].conflict_type == "signal_state_mismatch"
