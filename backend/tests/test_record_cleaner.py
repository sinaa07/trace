from app.core.cleaning.record_cleaner import RecordCleaner
from app.models.enums import SourceType


def test_timestamp_and_entity_normalization():
    cleaner = RecordCleaner()
    record = {
        "timestamp": "2024-03-15T08:12:10+05:30",
        "signal": "s42",
        "state": "RED",
        "train_id": "train-102",
    }
    cleaned = cleaner.clean_record(
        record, SourceType.SIGNAL_LOG, timezone_hint="Asia/Kolkata"
    )

    assert cleaned.is_valid
    assert cleaned.normalized_data["signal_id"] == "SIGNAL-S42"
    assert cleaned.normalized_data["train_id"] == "TRAIN-102"
    assert cleaned.normalized_data["timestamp"].endswith("+00:00")
    assert cleaned.field_provenance
    assert any(p["field"] == "train_id" for p in cleaned.field_provenance)


def test_malformed_record_retained_with_warnings():
    cleaner = RecordCleaner()
    record = {"timestamp": "not-a-date", "signal": "S42", "state": "RED"}
    cleaned = cleaner.clean_record(record, SourceType.SIGNAL_LOG)

    assert cleaned.is_valid is False
    assert cleaned.parse_warnings
    assert cleaned.raw_data == record
