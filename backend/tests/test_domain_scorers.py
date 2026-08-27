"""Unit tests for Phase 3 domain scorers and ranking."""

from datetime import datetime, timedelta, timezone

from app.core.investigation.ranking import score_hypothesis
from app.core.scorers import (
    AlertnessScorer,
    BehavioralTelemetryScorer,
    SignalRuleScorer,
    TrackConditionScorer,
    WeatherRiskScorer,
)
from app.schemas.investigation import HypothesisFindingCreate


def test_alertness_degrades_without_sleep_inputs():
    accident = datetime(2024, 6, 1, 4, 30, tzinfo=timezone.utc)
    result = AlertnessScorer().score(
        accident_time=accident,
        duty_hours=10.0,
    )
    assert result.domain == "fatigue"
    assert result.score is not None
    assert "circadian_time_of_day" in result.inputs_used
    assert "last_sleep_end" in result.missing_inputs
    assert any("Three-Process" in w for w in result.warnings)


def test_alertness_full_tpm_when_sleep_present():
    accident = datetime(2024, 6, 1, 4, 30, tzinfo=timezone.utc)
    result = AlertnessScorer().score(
        accident_time=accident,
        last_sleep_end=accident - timedelta(hours=8),
        sleep_duration_hours=5.0,
        duty_hours=8.0,
    )
    assert "homeostatic_s" in result.features
    assert "sleep_inertia_w" in result.features
    assert result.missing_inputs == []


def test_weather_threshold_scoring():
    result = WeatherRiskScorer().score(
        visibility_m=100.0,
        wind_speed_kmh=90.0,
        rainfall_mm_hour=10.0,
        ambient_temp_c=40.0,
    )
    assert result.score is not None
    assert result.score > 0
    assert result.features["visibility_m_exceeded"] is True
    assert result.features["wind_speed_kmh_exceeded"] is True


def test_track_overdue_without_qi():
    now = datetime(2024, 6, 1, tzinfo=timezone.utc)
    result = TrackConditionScorer().score(
        maintenance_due_at=now - timedelta(days=10),
        as_of=now,
    )
    assert result.features["maintenance_overdue"] is True
    assert result.score is not None


def test_track_qi_curve_fit():
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    points = [
        {"timestamp": base, "qi": 90},
        {"timestamp": base + timedelta(days=30), "qi": 70},
        {"timestamp": base + timedelta(days=60), "qi": 55},
    ]
    result = TrackConditionScorer().score(
        points,
        as_of=base + timedelta(days=90),
    )
    assert "estimated_qi" in result.features
    assert result.features["estimated_qi"] < 55


def test_behavioral_features_not_fatigue_verdict():
    samples = [{"speed": 80}, {"speed": 82}, {"speed": 79, "brake": "applied"}]
    result = BehavioralTelemetryScorer().score(samples, permitted_speed=100)
    assert result.features["brake_application_count"] == 1
    assert any("not" in w.lower() for w in result.warnings)


def test_signal_rule_scorer():
    result = SignalRuleScorer().score(
        [
            {"rule_id": "invalid_signal_transition", "title": "Bad transition"},
            {"rule_id": "speed_threshold_exceeded", "title": "Speed"},
        ]
    )
    assert result.features["signal_anomaly_count"] == 1
    assert result.score is not None


def test_ranking_penalizes_contradictions():
    finding = HypothesisFindingCreate(
        domain="fatigue",
        hypothesis="Driver fatigue contributed",
        reasoning="step by step",
        supporting_evidence=["e1", "e2", "e3"],
        contradicting_evidence=["c1", "c2"],
        missing_evidence=["m1"],
        confidence=0.8,
    )
    dims, score = score_hypothesis(finding)
    assert dims.contradiction_penalty == 1.0
    assert 0.0 <= score <= 1.0
