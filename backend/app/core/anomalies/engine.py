from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml

from app.models import AnomalySeverity, Event

RULES_PATH = Path(__file__).parent / "rules" / "railway_rules.yaml"


@dataclass
class AnomalyFinding:
    rule_id: str
    severity: AnomalySeverity
    title: str
    explanation: str
    affected_event_ids: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    details: dict[str, Any] | None = None


class AnomalyRuleEngine:
    def __init__(self, rules_path: Path | None = None) -> None:
        self.rules = self._load_rules(rules_path or RULES_PATH)

    @staticmethod
    def _load_rules(path: Path) -> list[dict[str, Any]]:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return list(data.get("rules") or [])

    def evaluate(self, events: list[Event]) -> list[AnomalyFinding]:
        findings: list[AnomalyFinding] = []
        for rule in self.rules:
            rule_type = rule.get("type")
            if rule_type == "clock_backward":
                findings.extend(self._clock_backward(rule, events))
            elif rule_type == "speed_threshold":
                findings.extend(self._speed_threshold(rule, events))
            elif rule_type == "brake_sequence":
                findings.extend(self._brake_sequence(rule, events))
            elif rule_type == "signal_transition":
                findings.extend(self._signal_transition(rule, events))
        return findings

    def _clock_backward(self, rule: dict, events: list[Event]) -> list[AnomalyFinding]:
        findings: list[AnomalyFinding] = []
        by_evidence: dict[str, list[Event]] = {}
        for event in events:
            if event.corrected_timestamp is None:
                continue
            key = str(event.evidence_id)
            by_evidence.setdefault(key, []).append(event)

        for evidence_id, group in by_evidence.items():
            ordered = sorted(group, key=lambda e: e.corrected_timestamp or datetime.min)
            for prev, curr in zip(ordered, ordered[1:]):
                if curr.corrected_timestamp < prev.corrected_timestamp:
                    findings.append(
                        AnomalyFinding(
                            rule_id=rule["id"],
                            severity=AnomalySeverity(rule["severity"]),
                            title=rule["title"],
                            explanation=(
                                f"Event {curr.event_id} occurs before prior event "
                                f"{prev.event_id} within evidence {evidence_id}."
                            ),
                            affected_event_ids=[str(prev.event_id), str(curr.event_id)],
                            evidence_refs=[evidence_id],
                            details={
                                "previous_timestamp": prev.corrected_timestamp.isoformat(),
                                "current_timestamp": curr.corrected_timestamp.isoformat(),
                            },
                        )
                    )
        return findings

    def _speed_threshold(self, rule: dict, events: list[Event]) -> list[AnomalyFinding]:
        params = rule.get("params") or {}
        max_speed = float(params.get("max_speed_kmh", 120))
        event_type = params.get("event_type", "SPEED_SAMPLE")
        speed_field = params.get("speed_field", "speed")
        findings: list[AnomalyFinding] = []

        for event in events:
            if event.event_type != event_type:
                continue
            speed = event.attributes.get(speed_field)
            try:
                speed_val = float(speed)
            except (TypeError, ValueError):
                continue
            if speed_val > max_speed:
                findings.append(
                    AnomalyFinding(
                        rule_id=rule["id"],
                        severity=AnomalySeverity(rule["severity"]),
                        title=rule["title"],
                        explanation=(
                            f"Entity {event.entity_id or 'unknown'} recorded speed "
                            f"{speed_val} km/h exceeding threshold {max_speed} km/h."
                        ),
                        affected_event_ids=[str(event.event_id)],
                        evidence_refs=[str(e) for e in (event.evidence_refs or [])],
                        details={"speed_kmh": speed_val, "threshold_kmh": max_speed},
                    )
                )
        return findings

    def _brake_sequence(self, rule: dict, events: list[Event]) -> list[AnomalyFinding]:
        params = rule.get("params") or {}
        event_type = params.get("event_type", "BRAKE_STATUS")
        applied = str(params.get("applied_value", "applied")).lower()
        released = str(params.get("released_value", "released")).lower()
        findings: list[AnomalyFinding] = []

        by_entity: dict[str, list[Event]] = {}
        for event in events:
            if event.event_type != event_type or not event.entity_id:
                continue
            by_entity.setdefault(event.entity_id, []).append(event)

        for entity_id, group in by_entity.items():
            ordered = sorted(
                group,
                key=lambda e: e.corrected_timestamp or datetime.min,
            )
            last_applied: Event | None = None
            for event in ordered:
                status = str(event.attributes.get("brake_status", "")).lower()
                if status == applied:
                    last_applied = event
                elif status == released and last_applied is None:
                    findings.append(
                        AnomalyFinding(
                            rule_id=rule["id"],
                            severity=AnomalySeverity(rule["severity"]),
                            title=rule["title"],
                            explanation=(
                                f"Train {entity_id} shows brake release before any "
                                f"recorded application."
                            ),
                            affected_event_ids=[str(event.event_id)],
                            evidence_refs=[str(e) for e in (event.evidence_refs or [])],
                            details={"entity_id": entity_id, "brake_status": status},
                        )
                    )
                elif status == released and last_applied and event.corrected_timestamp:
                    if (
                        last_applied.corrected_timestamp
                        and event.corrected_timestamp < last_applied.corrected_timestamp
                    ):
                        findings.append(
                            AnomalyFinding(
                                rule_id=rule["id"],
                                severity=AnomalySeverity(rule["severity"]),
                                title=rule["title"],
                                explanation=(
                                    f"Train {entity_id} brake release at "
                                    f"{event.corrected_timestamp.isoformat()} precedes "
                                    f"application at {last_applied.corrected_timestamp.isoformat()}."
                                ),
                                affected_event_ids=[
                                    str(last_applied.event_id),
                                    str(event.event_id),
                                ],
                                evidence_refs=list(
                                    {
                                        *(str(e) for e in (last_applied.evidence_refs or [])),
                                        *(str(e) for e in (event.evidence_refs or [])),
                                    }
                                ),
                                details={"entity_id": entity_id},
                            )
                        )
        return findings

    def _signal_transition(self, rule: dict, events: list[Event]) -> list[AnomalyFinding]:
        params = rule.get("params") or {}
        event_type = params.get("event_type", "SIGNAL_STATE_CHANGE")
        source_field = params.get("source_field", "source_id")
        state_field = params.get("state_field", "state")
        forbidden = params.get("forbidden_transitions") or []
        findings: list[AnomalyFinding] = []

        by_source: dict[str, list[Event]] = {}
        for event in events:
            if event.event_type != event_type:
                continue
            source = event.source_id or event.attributes.get(source_field)
            if not source:
                continue
            by_source.setdefault(str(source), []).append(event)

        for source_id, group in by_source.items():
            ordered = sorted(
                group,
                key=lambda e: e.corrected_timestamp or datetime.min,
            )
            prev_state: str | None = None
            prev_event: Event | None = None
            for event in ordered:
                state = str(event.attributes.get(state_field, "")).upper()
                if prev_state and prev_event:
                    for transition in forbidden:
                        if (
                            prev_state == str(transition.get("from", "")).upper()
                            and state == str(transition.get("to", "")).upper()
                        ):
                            findings.append(
                                AnomalyFinding(
                                    rule_id=rule["id"],
                                    severity=AnomalySeverity(rule["severity"]),
                                    title=rule["title"],
                                    explanation=(
                                        f"Signal {source_id} transitioned directly from "
                                        f"{prev_state} to {state}."
                                    ),
                                    affected_event_ids=[
                                        str(prev_event.event_id),
                                        str(event.event_id),
                                    ],
                                    evidence_refs=list(
                                        {
                                            *(str(e) for e in (prev_event.evidence_refs or [])),
                                            *(str(e) for e in (event.evidence_refs or [])),
                                        }
                                    ),
                                    details={
                                        "source_id": source_id,
                                        "from_state": prev_state,
                                        "to_state": state,
                                    },
                                )
                            )
                prev_state = state
                prev_event = event
        return findings
