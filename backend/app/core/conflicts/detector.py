from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from app.models import ConflictSeverity, Event


@dataclass
class ConflictFinding:
    conflict_type: str
    severity: ConflictSeverity
    title: str
    explanation: str
    event_ids: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    details: dict[str, Any] | None = None


class ConflictDetector:
    """Detect contradictions across aligned timeline events from different evidence sources."""

    def __init__(self, alignment_tolerance_seconds: float = 5.0) -> None:
        self.tolerance = timedelta(seconds=alignment_tolerance_seconds)

    def evaluate(self, events: list[Event]) -> list[ConflictFinding]:
        findings: list[ConflictFinding] = []
        findings.extend(self._signal_state_conflicts(events))
        findings.extend(self._maintenance_sensor_conflicts(events))
        return findings

    def _signal_state_conflicts(self, events: list[Event]) -> list[ConflictFinding]:
        signal_events = [
            e
            for e in events
            if e.event_type == "SIGNAL_STATE_CHANGE"
            and e.corrected_timestamp
            and e.source_id
        ]
        findings: list[ConflictFinding] = []

        for i, left in enumerate(signal_events):
            for right in signal_events[i + 1 :]:
                if left.source_id != right.source_id:
                    continue
                if str(left.evidence_id) == str(right.evidence_id):
                    continue
                if not self._within_tolerance(left.corrected_timestamp, right.corrected_timestamp):
                    continue

                left_state = str(left.attributes.get("state", "")).upper()
                right_state = str(right.attributes.get("state", "")).upper()
                if not left_state or not right_state or left_state == right_state:
                    continue

                findings.append(
                    ConflictFinding(
                        conflict_type="signal_state_mismatch",
                        severity=ConflictSeverity.HIGH,
                        title="Conflicting signal states at aligned time",
                        explanation=(
                            f"Signal {left.source_id} reported {left_state} and {right_state} "
                            f"within {self.tolerance.total_seconds}s from different evidence sources."
                        ),
                        event_ids=[str(left.event_id), str(right.event_id)],
                        evidence_refs=list(
                            {
                                str(left.evidence_id),
                                str(right.evidence_id),
                            }
                        ),
                        details={
                            "source_id": left.source_id,
                            "state_a": left_state,
                            "state_b": right_state,
                            "timestamp_a": left.corrected_timestamp.isoformat(),
                            "timestamp_b": right.corrected_timestamp.isoformat(),
                        },
                    )
                )
        return findings

    def _maintenance_sensor_conflicts(self, events: list[Event]) -> list[ConflictFinding]:
        maintenance = [
            e
            for e in events
            if e.event_type == "MAINTENANCE_RECORD" and e.corrected_timestamp
        ]
        speed_events = [
            e
            for e in events
            if e.event_type == "SPEED_SAMPLE" and e.corrected_timestamp
        ]
        findings: list[ConflictFinding] = []

        for maint in maintenance:
            status = str(maint.attributes.get("status", "")).lower()
            if status not in {"normal", "ok", "pass"}:
                continue
            equipment = maint.attributes.get("equipment_id") or maint.source_id
            for speed in speed_events:
                if not self._within_tolerance(
                    maint.corrected_timestamp, speed.corrected_timestamp
                ):
                    continue
                try:
                    speed_val = float(speed.attributes.get("speed", 0))
                except (TypeError, ValueError):
                    continue
                if speed_val > 100:
                    findings.append(
                        ConflictFinding(
                            conflict_type="maintenance_vs_sensor",
                            severity=ConflictSeverity.MEDIUM,
                            title="Maintenance normal while sensor shows abnormal condition",
                            explanation=(
                                f"Maintenance record for {equipment or 'equipment'} reports "
                                f"normal while speed sample shows {speed_val} km/h."
                            ),
                            event_ids=[str(maint.event_id), str(speed.event_id)],
                            evidence_refs=list(
                                {
                                    str(maint.evidence_id),
                                    str(speed.evidence_id),
                                }
                            ),
                            details={
                                "equipment_id": equipment,
                                "maintenance_status": status,
                                "speed_kmh": speed_val,
                            },
                        )
                    )
        return findings

    def _within_tolerance(self, left, right) -> bool:
        delta = abs(left - right)
        return delta <= self.tolerance
