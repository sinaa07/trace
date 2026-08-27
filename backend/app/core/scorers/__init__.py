"""Domain feature scorers for Phase 3 investigation preprocessors.

Deterministic / statistical only — no trained ML, no LLM.
Outputs feed agent context; they never become evidence themselves.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass
class DomainFeatureResult:
    domain: str
    score: float | None
    summary: str
    features: dict[str, Any] = field(default_factory=dict)
    inputs_used: list[str] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AlertnessScorer:
    """Degraded Three-Process alertness.

    Always: hours-of-service check + circadian C(t).
    Full TPM (S + W) only when sleep end / duration are available.
    """

    MAX_DUTY_HOURS = 9.0
    CIRCADIAN_PEAK_HOUR = 14.0
    CIRCADIAN_TROUGH_HOUR = 4.0

    def score(
        self,
        *,
        accident_time: datetime | None,
        shift_start: datetime | None = None,
        last_sleep_end: datetime | None = None,
        sleep_duration_hours: float | None = None,
        duty_hours: float | None = None,
    ) -> DomainFeatureResult:
        missing: list[str] = []
        used: list[str] = []
        warnings: list[str] = []
        features: dict[str, Any] = {}

        accident = _as_utc(accident_time)
        if accident is None:
            missing.append("accident_time")
            return DomainFeatureResult(
                domain="fatigue",
                score=None,
                summary="Cannot compute alertness without accident_time.",
                missing_inputs=missing,
                warnings=["accident_time required"],
            )

        used.append("accident_time")
        hour = accident.hour + accident.minute / 60.0
        # Circadian component: peak ~14:00, trough ~04:00 → map to 0..1 alertness contrib
        circadian = 0.5 + 0.5 * math.cos(
            2 * math.pi * (hour - self.CIRCADIAN_PEAK_HOUR) / 24.0
        )
        features["circadian_c"] = round(circadian, 4)
        used.append("circadian_time_of_day")

        if duty_hours is None and shift_start is not None:
            start = _as_utc(shift_start)
            if start is not None:
                duty_hours = max((accident - start).total_seconds() / 3600.0, 0.0)
                used.append("shift_start")
        if duty_hours is not None:
            features["duty_hours"] = round(duty_hours, 3)
            used.append("duty_hours")
            features["duty_exceeds_limit"] = duty_hours > self.MAX_DUTY_HOURS
        else:
            missing.append("duty_hours_or_shift_start")

        homeostatic = None
        sleep_inertia = None
        if last_sleep_end is not None and sleep_duration_hours is not None:
            sleep_end = _as_utc(last_sleep_end)
            if sleep_end is not None:
                hours_awake = max((accident - sleep_end).total_seconds() / 3600.0, 0.0)
                # Linear decay from rested baseline; reset magnitude scales with sleep length
                sleep_credit = min(max(sleep_duration_hours / 8.0, 0.0), 1.2)
                homeostatic = max(1.0 - (hours_awake / 18.0) * sleep_credit, 0.0)
                # Sleep inertia decays exponentially in first ~2h after waking
                sleep_inertia = math.exp(-hours_awake / 0.7) * 0.35
                features["hours_awake"] = round(hours_awake, 3)
                features["homeostatic_s"] = round(homeostatic, 4)
                features["sleep_inertia_w"] = round(sleep_inertia, 4)
                used.extend(["last_sleep_end", "sleep_duration_hours"])
        else:
            missing.extend(
                [
                    m
                    for m in ("last_sleep_end", "sleep_duration_hours")
                    if (m == "last_sleep_end" and last_sleep_end is None)
                    or (m == "sleep_duration_hours" and sleep_duration_hours is None)
                ]
            )
            warnings.append(
                "Full Three-Process Model unavailable; using circadian + duty only."
            )

        # Composite alertness 0..1 (higher = more alert)
        components = [circadian]
        if homeostatic is not None and sleep_inertia is not None:
            components.append(max(homeostatic - sleep_inertia, 0.0))
        if duty_hours is not None:
            duty_penalty = min(duty_hours / (self.MAX_DUTY_HOURS * 1.5), 1.0)
            components.append(1.0 - duty_penalty)

        alertness = sum(components) / len(components)
        features["alertness_score"] = round(alertness, 4)
        fatigue_risk = round(1.0 - alertness, 4)

        return DomainFeatureResult(
            domain="fatigue",
            score=fatigue_risk,
            summary=(
                f"Fatigue risk {fatigue_risk:.2f} "
                f"(alertness {alertness:.2f}; circadian {circadian:.2f}"
                + (
                    f"; duty {duty_hours:.1f}h"
                    if duty_hours is not None
                    else ""
                )
                + ")."
            ),
            features=features,
            inputs_used=sorted(set(used)),
            missing_inputs=sorted(set(missing)),
            warnings=warnings,
        )


class BehavioralTelemetryScorer:
    """Statistical loco features in a pre-accident window. Features only — no causal verdict."""

    def score(
        self,
        speed_samples: list[dict[str, Any]],
        *,
        permitted_speed: float | None = None,
        window_minutes: float = 15.0,
    ) -> DomainFeatureResult:
        missing: list[str] = []
        used: list[str] = []
        features: dict[str, Any] = {"window_minutes": window_minutes}

        if not speed_samples:
            missing.append("speed_samples")
            return DomainFeatureResult(
                domain="behavioral_telemetry",
                score=None,
                summary="No speed samples available for behavioral analysis.",
                missing_inputs=missing,
            )

        speeds: list[float] = []
        for sample in speed_samples:
            try:
                speeds.append(float(sample.get("speed")))
            except (TypeError, ValueError):
                continue

        if not speeds:
            missing.append("numeric_speed")
            return DomainFeatureResult(
                domain="behavioral_telemetry",
                score=None,
                summary="Speed samples present but no numeric speed values.",
                missing_inputs=missing,
                warnings=["Could not parse speed values"],
            )

        used.append("speed_samples")
        mean_speed = sum(speeds) / len(speeds)
        variance = sum((s - mean_speed) ** 2 for s in speeds) / len(speeds)
        features["sample_count"] = len(speeds)
        features["mean_speed"] = round(mean_speed, 3)
        features["speed_variance"] = round(variance, 4)
        features["speed_std"] = round(math.sqrt(variance), 4)

        if permitted_speed is not None and permitted_speed > 0:
            used.append("permitted_speed")
            deviations = [abs(s - permitted_speed) for s in speeds]
            features["mean_abs_deviation_from_permitted"] = round(
                sum(deviations) / len(deviations), 3
            )
            features["max_excess_over_permitted"] = round(
                max(0.0, max(speeds) - permitted_speed), 3
            )
        else:
            missing.append("permitted_speed")

        throttle_changes = sum(
            1
            for sample in speed_samples
            if sample.get("throttle_change") or sample.get("throttle_event")
        )
        brake_events = sum(
            1
            for sample in speed_samples
            if str(sample.get("brake", "")).lower() in {"applied", "1", "true"}
            or sample.get("brake_event")
        )
        features["throttle_adjustment_count"] = throttle_changes
        features["brake_application_count"] = brake_events
        if throttle_changes:
            used.append("throttle_events")
        else:
            missing.append("throttle_events")
        if brake_events:
            used.append("brake_events")
        else:
            missing.append("brake_events")

        # Intensity score: higher variance / activity — not a fatigue verdict
        intensity = min(math.sqrt(variance) / 20.0, 1.0)
        return DomainFeatureResult(
            domain="behavioral_telemetry",
            score=round(intensity, 4),
            summary=(
                f"Behavioral window: n={len(speeds)}, mean_speed={mean_speed:.1f}, "
                f"std={math.sqrt(variance):.2f}, brakes={brake_events}."
            ),
            features=features,
            inputs_used=sorted(set(used)),
            missing_inputs=sorted(set(missing)),
            warnings=[
                "Behavioral features are descriptive only; do not treat as fatigue proof."
            ],
        )


class WeatherRiskScorer:
    """Threshold composite weather risk from operational rules."""

    VISIBILITY_SEVERE_M = 200.0
    WIND_HIGH_KMH = 80.0
    RAIL_TEMP_BUCKLE_C = 55.0
    RAINFALL_WASHOUT_MMH = 50.0

    def score(
        self,
        *,
        visibility_m: float | None = None,
        wind_speed_kmh: float | None = None,
        ambient_temp_c: float | None = None,
        rail_temp_c: float | None = None,
        rainfall_mm_hour: float | None = None,
    ) -> DomainFeatureResult:
        used: list[str] = []
        missing: list[str] = []
        features: dict[str, Any] = {}
        exceedances: list[str] = []
        weighted = 0.0
        weight_total = 0.0

        checks = [
            ("visibility_m", visibility_m, self.VISIBILITY_SEVERE_M, True, 0.3),
            ("wind_speed_kmh", wind_speed_kmh, self.WIND_HIGH_KMH, False, 0.25),
            ("rainfall_mm_hour", rainfall_mm_hour, self.RAINFALL_WASHOUT_MMH, False, 0.25),
        ]
        for name, value, threshold, below, weight in checks:
            weight_total += weight
            if value is None:
                missing.append(name)
                continue
            used.append(name)
            features[name] = value
            features[f"{name}_threshold"] = threshold
            exceeded = value < threshold if below else value > threshold
            features[f"{name}_exceeded"] = exceeded
            if exceeded:
                exceedances.append(name)
                weighted += weight

        # Rail temperature: prefer measured rail temp; else ambient + 15°C solar estimate
        weight_total += 0.2
        estimated_rail = None
        if rail_temp_c is not None:
            estimated_rail = rail_temp_c
            used.append("rail_temp_c")
        elif ambient_temp_c is not None:
            estimated_rail = ambient_temp_c + 15.0
            used.append("ambient_temp_c")
            features["rail_temp_estimated_from_ambient"] = True
        else:
            missing.extend(["rail_temp_c", "ambient_temp_c"])

        if estimated_rail is not None:
            features["rail_temp_c"] = round(estimated_rail, 2)
            features["rail_temp_threshold"] = self.RAIL_TEMP_BUCKLE_C
            buckle = estimated_rail > self.RAIL_TEMP_BUCKLE_C
            features["rail_temp_exceeded"] = buckle
            if buckle:
                exceedances.append("rail_temp_c")
                weighted += 0.2

        score = weighted / weight_total if weight_total else None
        if not used:
            return DomainFeatureResult(
                domain="weather",
                score=None,
                summary="No weather measurements available for threshold scoring.",
                missing_inputs=missing,
            )

        return DomainFeatureResult(
            domain="weather",
            score=round(score or 0.0, 4),
            summary=(
                f"Weather risk {score:.2f}; exceedances: "
                + (", ".join(exceedances) if exceedances else "none")
                + "."
            ),
            features=features,
            inputs_used=sorted(set(used)),
            missing_inputs=sorted(set(missing)),
        )


class TrackConditionScorer:
    """QI curve fit when enough points exist; else overdue-maintenance / threshold flags."""

    QI_THRESHOLD = 40.0

    def score(
        self,
        qi_points: list[dict[str, Any]] | None = None,
        *,
        maintenance_due_at: datetime | None = None,
        as_of: datetime | None = None,
        last_maintenance_at: datetime | None = None,
    ) -> DomainFeatureResult:
        used: list[str] = []
        missing: list[str] = []
        warnings: list[str] = []
        features: dict[str, Any] = {"qi_threshold": self.QI_THRESHOLD}
        as_of_dt = _as_utc(as_of) or datetime.now(timezone.utc)

        overdue = None
        if maintenance_due_at is not None:
            due = _as_utc(maintenance_due_at)
            if due is not None:
                overdue = as_of_dt > due
                features["maintenance_overdue"] = overdue
                features["maintenance_due_at"] = due.isoformat()
                used.append("maintenance_due_at")
        else:
            missing.append("maintenance_due_at")

        if last_maintenance_at is not None:
            last = _as_utc(last_maintenance_at)
            if last is not None:
                features["days_since_maintenance"] = round(
                    (as_of_dt - last).total_seconds() / 86400.0, 2
                )
                used.append("last_maintenance_at")
        else:
            missing.append("last_maintenance_at")

        series: list[tuple[float, float]] = []
        for point in qi_points or []:
            try:
                ts = point.get("timestamp") or point.get("t")
                qi = float(point.get("qi") if "qi" in point else point.get("quality_index"))
                if isinstance(ts, datetime):
                    t = _as_utc(ts)
                else:
                    t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    t = _as_utc(t)
                if t is None:
                    continue
                series.append((t.timestamp(), qi))
            except (TypeError, ValueError):
                continue

        estimated_qi = None
        slope = None
        if len(series) >= 2:
            used.append("qi_points")
            series.sort(key=lambda p: p[0])
            t0 = series[0][0]
            xs = [p[0] - t0 for p in series]
            ys = [p[1] for p in series]
            # Fit QI(t) = QI0 * exp(-λt) in log space when all positive
            if all(y > 0 for y in ys):
                # linear regression on log(y) = log(QI0) - λx
                n = len(xs)
                mean_x = sum(xs) / n
                log_ys = [math.log(y) for y in ys]
                mean_log = sum(log_ys) / n
                denom = sum((x - mean_x) ** 2 for x in xs) or 1.0
                slope_log = sum((x - mean_x) * (ly - mean_log) for x, ly in zip(xs, log_ys)) / denom
                intercept = mean_log - slope_log * mean_x
                lam = -slope_log
                qi0 = math.exp(intercept)
                dt = as_of_dt.timestamp() - t0
                estimated_qi = qi0 * math.exp(-lam * dt)
                slope = -lam * estimated_qi  # dQI/dt at as_of
                features["qi0"] = round(qi0, 3)
                features["lambda"] = round(lam, 8)
                features["estimated_qi"] = round(estimated_qi, 3)
                features["qi_slope_at_as_of"] = round(slope, 6)
                features["below_threshold"] = estimated_qi < self.QI_THRESHOLD
            else:
                warnings.append("Non-positive QI values; skipped exponential fit.")
                missing.append("positive_qi_series")
        else:
            missing.append("qi_points")
            warnings.append(
                "Insufficient QI history for curve fit; using maintenance flags only."
            )

        # Risk score: overdue + below threshold + steep decline
        risk = 0.0
        parts = 0
        if overdue is not None:
            parts += 1
            risk += 1.0 if overdue else 0.0
        if estimated_qi is not None:
            parts += 1
            risk += 1.0 if estimated_qi < self.QI_THRESHOLD else 0.0
            if slope is not None and slope < -0.05:
                parts += 1
                risk += 1.0

        score = risk / parts if parts else None
        return DomainFeatureResult(
            domain="track",
            score=round(score, 4) if score is not None else None,
            summary=(
                "Track condition: "
                + (
                    f"estimated QI {estimated_qi:.1f}"
                    if estimated_qi is not None
                    else "no QI estimate"
                )
                + (
                    f"; maintenance overdue={overdue}"
                    if overdue is not None
                    else ""
                )
                + "."
            ),
            features=features,
            inputs_used=sorted(set(used)),
            missing_inputs=sorted(set(missing)),
            warnings=warnings,
        )


class SignalRuleScorer:
    """Summarize signal FSM / rule violations already detected by the anomaly engine."""

    def score(self, anomalies: list[dict[str, Any]]) -> DomainFeatureResult:
        signal_anomalies = [
            a
            for a in anomalies
            if a.get("rule_id") == "invalid_signal_transition"
            or "signal" in str(a.get("rule_id", "")).lower()
            or "signal" in str(a.get("title", "")).lower()
        ]
        features = {
            "signal_anomaly_count": len(signal_anomalies),
            "total_anomaly_count": len(anomalies),
            "rule_ids": sorted(
                {str(a.get("rule_id")) for a in signal_anomalies if a.get("rule_id")}
            ),
        }
        score = min(len(signal_anomalies) / 3.0, 1.0) if anomalies else 0.0
        return DomainFeatureResult(
            domain="signalling",
            score=round(score, 4),
            summary=(
                f"{len(signal_anomalies)} signal-rule anomaly(ies) among "
                f"{len(anomalies)} total anomalies."
            ),
            features=features,
            inputs_used=["anomalies"] if anomalies else [],
            missing_inputs=[] if anomalies else ["anomalies"],
        )
