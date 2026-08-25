"""Affine clock models and temporal reconstruction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from app.core.events.extractor import EventDraft


@dataclass
class ClockModel:
    drift_factor: float = 1.0
    offset_seconds: float = 0.0
    inferred: bool = False


@dataclass
class CorrectedEventDraft:
    draft: EventDraft
    corrected_timestamp: datetime | None
    clock_offset_seconds: float | None
    clock_drift_factor: float | None
    temporal_confidence: float


@dataclass
class TimelineResult:
    events: list[CorrectedEventDraft] = field(default_factory=list)
    clock_models_by_evidence: dict[str, ClockModel] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class TemporalEngine:
    """Temporal engine: affine correction (a * t + b) + unified timeline ordering."""

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

        clock_models: dict[str, ClockModel] = {}
        for evidence_id, group in by_evidence.items():
            meta = evidence_metadata.get(evidence_id, {})
            clock_models[evidence_id] = self._resolve_clock_model(
                meta, group, incident_time
            )

        result.clock_models_by_evidence = clock_models

        for draft in drafts:
            evidence_id = str(draft.evidence_id)
            model = clock_models.get(evidence_id, ClockModel())
            corrected, confidence = self._apply_affine_correction(draft, model)
            offset = model.offset_seconds if model.offset_seconds else None
            drift = model.drift_factor if model.drift_factor != 1.0 else None
            if model.inferred and (offset or drift):
                confidence = min(confidence, 0.85)
            result.events.append(
                CorrectedEventDraft(
                    draft=draft,
                    corrected_timestamp=corrected,
                    clock_offset_seconds=offset,
                    clock_drift_factor=drift or (1.0 if model.inferred else None),
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

    def _resolve_clock_model(
        self,
        meta: dict[str, Any],
        group: list[EventDraft],
        incident_time: datetime | None,
    ) -> ClockModel:
        drift = float(meta.get("clock_drift_factor") or 1.0)
        offset = float(meta.get("clock_offset_seconds") or 0.0)
        if meta.get("clock_drift_factor") is not None or meta.get("clock_offset_seconds"):
            return ClockModel(
                drift_factor=drift,
                offset_seconds=offset,
                inferred=False,
            )

        anchors = meta.get("clock_anchors")
        if isinstance(anchors, list) and len(anchors) >= 2:
            model = self._fit_affine_from_anchors(anchors)
            if model:
                return model

        if incident_time is not None:
            offset = self._estimate_anchor_offset(group, incident_time)
            return ClockModel(drift_factor=1.0, offset_seconds=offset, inferred=True)

        return ClockModel(drift_factor=1.0, offset_seconds=0.0, inferred=False)

    @staticmethod
    def _fit_affine_from_anchors(anchors: list[dict[str, Any]]) -> ClockModel | None:
        raw_epochs: list[float] = []
        true_epochs: list[float] = []
        for anchor in anchors:
            raw_ts = TemporalEngine._parse_anchor_ts(anchor.get("raw"))
            true_ts = TemporalEngine._parse_anchor_ts(anchor.get("true"))
            if raw_ts is None or true_ts is None:
                continue
            raw_epochs.append(raw_ts.timestamp())
            true_epochs.append(true_ts.timestamp())

        if len(raw_epochs) < 2:
            return None

        drift, offset = np.polyfit(raw_epochs, true_epochs, 1)
        return ClockModel(
            drift_factor=float(drift),
            offset_seconds=float(offset),
            inferred=True,
        )

    @staticmethod
    def _parse_anchor_ts(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            ts = value
        else:
            try:
                ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)

    @staticmethod
    def _estimate_anchor_offset(
        group: list[EventDraft], incident_time: datetime
    ) -> float:
        if incident_time.tzinfo is None:
            incident_time = incident_time.replace(tzinfo=timezone.utc)

        timestamps = [d.raw_timestamp for d in group if d.raw_timestamp]
        if not timestamps:
            return 0.0
        timestamps.sort()
        median = timestamps[len(timestamps) // 2]
        if median.tzinfo is None:
            median = median.replace(tzinfo=timezone.utc)
        return (incident_time - median).total_seconds()

    @staticmethod
    def _apply_affine_correction(
        draft: EventDraft, model: ClockModel
    ) -> tuple[datetime | None, float]:
        if draft.raw_timestamp is None:
            return None, 0.3

        ts = draft.raw_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        raw_epoch = ts.timestamp()
        corrected_epoch = model.drift_factor * raw_epoch + model.offset_seconds
        corrected = datetime.fromtimestamp(corrected_epoch, tz=timezone.utc)

        confidence = draft.temporal_confidence
        if model.drift_factor != 1.0 or model.offset_seconds != 0.0:
            confidence = min(confidence, 0.9 if not model.inferred else 0.85)
        return corrected, confidence
