"""Compute Phase 3 domain feature bundles from case evidence/events."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.scorers import (
    AlertnessScorer,
    BehavioralTelemetryScorer,
    SignalRuleScorer,
    TrackConditionScorer,
    WeatherRiskScorer,
)
from app.models.enums import SourceType
from app.schemas.investigation import DomainFeatureResultModel, DomainFeaturesResponse
from app.services.event_service import EventService
from app.services.quality_service import QualityAnalysisService
from app.services.storage.repositories.case_repo import CaseRepository
from app.services.storage.repositories.evidence_repo import EvidenceRepository


class DomainFeatureService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.cases = CaseRepository(db)
        self.evidence = EvidenceRepository(db)
        self.events = EventService(db)
        self.quality = QualityAnalysisService(db)
        self.alertness = AlertnessScorer()
        self.behavioral = BehavioralTelemetryScorer()
        self.weather = WeatherRiskScorer()
        self.track = TrackConditionScorer()
        self.signal = SignalRuleScorer()

    def compute_for_case(self, case_id: uuid.UUID) -> DomainFeaturesResponse | None:
        case = self.cases.get(case_id)
        if not case:
            return None

        notes: list[str] = []
        metadata = case.metadata_ or {}
        try:
            duty_meta = metadata.get("duty") if isinstance(metadata.get("duty"), dict) else {}
            weather_meta = (
                metadata.get("weather") if isinstance(metadata.get("weather"), dict) else {}
            )
            track_meta = (
                metadata.get("track") if isinstance(metadata.get("track"), dict) else {}
            )

            # Pull weather/track from evidence records when metadata absent
            weather_from_records = self._extract_weather_from_records(case_id)
            track_from_records = self._extract_track_from_records(case_id)
            speed_samples = self._extract_speed_samples(case_id)

            alertness = self.alertness.score(
                accident_time=case.incident_time,
                shift_start=self._parse_dt(duty_meta.get("shift_start")),
                last_sleep_end=self._parse_dt(duty_meta.get("last_sleep_end")),
                sleep_duration_hours=self._as_float(duty_meta.get("sleep_duration_hours")),
                duty_hours=self._as_float(duty_meta.get("duty_hours")),
            )
            behavioral = self.behavioral.score(
                speed_samples,
                permitted_speed=self._as_float(
                    duty_meta.get("permitted_speed")
                    or metadata.get("permitted_speed_kmh")
                ),
            )
            weather = self.weather.score(
                visibility_m=self._as_float(
                    weather_meta.get("visibility_m") or weather_from_records.get("visibility_m")
                ),
                wind_speed_kmh=self._as_float(
                    weather_meta.get("wind_speed_kmh")
                    or weather_from_records.get("wind_speed_kmh")
                ),
                ambient_temp_c=self._as_float(
                    weather_meta.get("ambient_temp_c")
                    or weather_from_records.get("ambient_temp_c")
                    or weather_from_records.get("temperature_c")
                ),
                rail_temp_c=self._as_float(
                    weather_meta.get("rail_temp_c") or weather_from_records.get("rail_temp_c")
                ),
                rainfall_mm_hour=self._as_float(
                    weather_meta.get("rainfall_mm_hour")
                    or weather_from_records.get("rainfall_mm_hour")
                ),
            )
            track = self.track.score(
                qi_points=track_meta.get("qi_points") or track_from_records.get("qi_points"),
                maintenance_due_at=self._parse_dt(
                    track_meta.get("maintenance_due_at")
                    or track_from_records.get("maintenance_due_at")
                ),
                as_of=case.incident_time,
                last_maintenance_at=self._parse_dt(
                    track_meta.get("last_maintenance_at")
                    or track_from_records.get("last_maintenance_at")
                ),
            )

            anomalies = [
                {
                    "rule_id": a.rule_id,
                    "title": a.title,
                    "severity": getattr(a.severity, "value", a.severity),
                }
                for a in self.quality.get_anomalies(case_id)
            ]
            signalling = self.signal.score(anomalies)

            domains = [
                DomainFeatureResultModel.model_validate(alertness.to_dict()),
                DomainFeatureResultModel.model_validate(behavioral.to_dict()),
                DomainFeatureResultModel.model_validate(signalling.to_dict()),
                DomainFeatureResultModel.model_validate(track.to_dict()),
                DomainFeatureResultModel.model_validate(weather.to_dict()),
            ]
            notes.append(
                "Domain features are deterministic preprocessors for Phase 3 agents; "
                "scores are not Bayesian probabilities."
            )
            return DomainFeaturesResponse(
                case_id=case_id,
                generated_at=datetime.now(timezone.utc),
                domains=domains,
                notes=notes,
            )
        except Exception as exc:
            notes.append(f"Partial failure computing domain features: {exc}")
            return DomainFeaturesResponse(
                case_id=case_id,
                generated_at=datetime.now(timezone.utc),
                domains=[],
                notes=notes,
            )

    def _extract_speed_samples(self, case_id: uuid.UUID) -> list[dict[str, Any]]:
        samples: list[dict[str, Any]] = []
        for event in self.events.get_case_events(case_id, event_type="SPEED_SAMPLE"):
            attrs = event.attributes or {}
            samples.append(
                {
                    "speed": attrs.get("speed") or attrs.get("speed_kmh"),
                    "brake": attrs.get("brake") or attrs.get("brake_status"),
                    "throttle_change": attrs.get("throttle_change"),
                    "brake_event": attrs.get("brake_event"),
                    "timestamp": event.corrected_timestamp or event.raw_timestamp,
                }
            )
        return samples

    def _extract_weather_from_records(self, case_id: uuid.UUID) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for artifact in self.evidence.list_artifacts_for_case(case_id):
            if artifact.source_type != SourceType.WEATHER:
                continue
            for record in self.evidence.list_records_for_evidence(
                artifact.evidence_id, valid_only=True
            ):
                data = record.normalized_data or {}
                for key in (
                    "visibility_m",
                    "wind_speed_kmh",
                    "ambient_temp_c",
                    "temperature_c",
                    "rail_temp_c",
                    "rainfall_mm_hour",
                ):
                    if key in data and out.get(key) is None:
                        out[key] = data[key]
        return out

    def _extract_track_from_records(self, case_id: uuid.UUID) -> dict[str, Any]:
        out: dict[str, Any] = {"qi_points": []}
        for artifact in self.evidence.list_artifacts_for_case(case_id):
            if artifact.source_type != SourceType.MAINTENANCE:
                continue
            for record in self.evidence.list_records_for_evidence(
                artifact.evidence_id, valid_only=True
            ):
                data = record.normalized_data or {}
                if "qi" in data or "quality_index" in data:
                    out["qi_points"].append(
                        {
                            "qi": data.get("qi", data.get("quality_index")),
                            "timestamp": data.get("timestamp")
                            or data.get("inspection_time")
                            or record.created_at,
                        }
                    )
                for key in ("maintenance_due_at", "last_maintenance_at"):
                    if key in data and out.get(key) is None:
                        out[key] = data[key]
        return out

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
