from app.core.processing.cleaner import DomainProcessor
from app.core.processing.registry import ProcessingProfileRegistry
from app.models.enums import SourceType


def test_registry_loads_all_source_type_profiles():
    registry = ProcessingProfileRegistry()
    ids = {p.id for p in registry.all_profiles()}
    assert {
        "signal_log_v1",
        "train_telemetry_v1",
        "maintenance_v1",
        "weather_v1",
        "witness_v1",
        "other_v1",
    }.issubset(ids)


def test_select_signal_log_profile_high_confidence():
    registry = ProcessingProfileRegistry()
    records = [
        {"timestamp": "2024-01-01T00:00:00Z", "signal": "S42", "state": "RED"},
        {"timestamp": "2024-01-01T00:00:01Z", "signal": "S42", "state": "GREEN"},
    ]
    selection = registry.select(
        SourceType.SIGNAL_LOG,
        filename="signal_log.csv",
        records=records,
    )
    assert selection.profile.id == "signal_log_v1"
    assert selection.match_score >= 0.35
    assert selection.needs_review is False
    assert any("header_match" in r for r in selection.match_reasons)


def test_declared_override_when_headers_disagree():
    registry = ProcessingProfileRegistry()
    # Looks like weather, but declared as signal_log → keep declared + needs_review
    records = [
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "temperature": 22.5,
            "rainfall": 3.1,
            "visibility": 4.0,
        }
    ]
    selection = registry.select(
        SourceType.SIGNAL_LOG,
        filename="weather_station.csv",
        records=records,
    )
    assert selection.profile.id == "signal_log_v1"
    assert selection.needs_review is True
    assert any("declared_override" in r or "low_confidence" in r for r in selection.match_reasons)


def test_domain_processor_cleans_with_signal_profile():
    processor = DomainProcessor()
    record = {
        "timestamp": "2024-03-15T08:12:10+05:30",
        "signal": "s42",
        "state": "RED",
        "train_id": "train-102",
    }
    cleaned, selection = processor.select_and_clean(
        [record],
        SourceType.SIGNAL_LOG,
        filename="signal_log.csv",
        source_metadata={"timezone": "Asia/Kolkata"},
    )
    assert selection.profile.id == "signal_log_v1"
    assert cleaned[0].is_valid
    assert cleaned[0].normalized_data["signal_id"] == "SIGNAL-S42"
    assert cleaned[0].normalized_data["train_id"] == "TRAIN-102"
    assert cleaned[0].normalized_data["timestamp"].endswith("+00:00")


def test_train_telemetry_profile_required_fields():
    processor = DomainProcessor()
    cleaned, selection = processor.select_and_clean(
        [{"timestamp": "2024-01-01T00:00:00Z", "speed": 80}],
        SourceType.TRAIN_TELEMETRY,
        filename="train_telemetry.json",
    )
    assert selection.profile.id == "train_telemetry_v1"
    assert cleaned[0].is_valid is False
    assert any("Missing required fields" in w for w in (cleaned[0].parse_warnings or []))
