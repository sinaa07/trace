"""Temporal reconstruction: apply clock offsets and build unified timeline order."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.events.extractor import EventDraft


@dataclass
class CorrectedEventDraft:
    draft: EventDraft
    corrected_timestamp: datetime | None
    clock_offset_seconds: float | None
    temporal_confidence: float


@dataclass
class TimelineResult:
    events: list[CorrectedEventDraft] = field(default_factory=list)
    offsets_by_evidence: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class TemporalEngine:
    """MVP temporal engine: metadata offsets + optional incident anchor alignment."""

    def reconstruct(
        self,
        drafts: list[EventDraft],
        *,
        incident_time: datetime | None = None,
        evidence_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> TimelineResult:
        evidence_metadata = evidence_metadata or {}
        result = TimelineResult()
        by_evidence: dict[str, list[EventDraft]] = {}

        for draft in drafts:
            key = str(draft.evidence_id)
            by_evidence.setdefault(key, []).append(draft)

        offsets: dict[str, float] = {}
        for evidence_id, group in by_evidence.items():
            meta = evidence_metadata.get(evidence_id, {})
            offset = float(meta.get("clock_offset_seconds") or 0.0)
            offsets[evidence_id] = offset

        if incident_time is not None:
            anchor_offsets = self._estimate_anchor_offsets(by_evidence, incident_time)
            for evidence_id, anchor_offset in anchor_offsets.items():
                if evidence_id not in evidence_metadata or not evidence_metadata[
                    evidence_id
                ].get("clock_offset_seconds"):
                    offsets[evidence_id] = anchor_offset

        result.offsets_by_evidence = offsets

        for draft in drafts:
            evidence_id = str(draft.evidence_id)
            offset = offsets.get(evidence_id, 0.0)
            corrected, confidence = self._apply_correction(draft, offset)
            result.events.append(
                CorrectedEventDraft(
                    draft=draft,
                    corrected_timestamp=corrected,
                    clock_offset_seconds=offset if offset else None,
                    temporal_confidence=min(draft.temporal_confidence, confidence),
                )
            )

        result.events.sort(
            key=lambda e: (
                e.corrected_timestamp is None,
                e.corrected_timestamp or datetime.min.replace(tzinfo=timezone.utc),
            )
        )
        return result

    @staticmethod
    def _estimate_anchor_offsets(
        by_evidence: dict[str, list[EventDraft]], incident_time: datetime
    ) -> dict[str, float]:
        """Align each evidence source median timestamp toward incident_time."""
        offsets: dict[str, float] = {}
        if incident_time.tzinfo is None:
            incident_time = incident_time.replace(tzinfo=timezone.utc)

        for evidence_id, group in by_evidence.items():
            timestamps = [d.raw_timestamp for d in group if d.raw_timestamp]
            if not timestamps:
                continue
            timestamps.sort()
            median = timestamps[len(timestamps) // 2]
            if median.tzinfo is None:
                median = median.replace(tzinfo=timezone.utc)
            delta = incident_time - median
            offsets[evidence_id] = delta.total_seconds()
        return offsets

    @staticmethod
    def _apply_correction(
        draft: EventDraft, offset_seconds: float
    ) -> tuple[datetime | None, float]:
        if draft.raw_timestamp is None:
            return None, 0.3

        ts = draft.raw_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        corrected = ts + timedelta(seconds=offset_seconds)
        confidence = draft.temporal_confidence
        if offset_seconds != 0:
            confidence = min(confidence, 0.85)
        return corrected, confidence
