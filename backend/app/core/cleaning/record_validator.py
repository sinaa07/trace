from dataclasses import dataclass, field
from typing import Any

from app.models.enums import SourceType


@dataclass
class CleanedRecord:
    raw_data: dict[str, Any]
    normalized_data: dict[str, Any]
    field_provenance: list[dict[str, Any]] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)
    is_valid: bool = True


def validate_record(source_type: SourceType, normalized: dict[str, Any]) -> tuple[bool, list[str]]:
    """Legacy validator; DomainProcessor validates via ProcessingProfile.required_fields."""
    warnings: list[str] = []
    required_by_type = {
        SourceType.SIGNAL_LOG: ["timestamp", "signal_id", "state"],
        SourceType.TRAIN_TELEMETRY: ["timestamp", "train_id"],
        SourceType.MAINTENANCE: ["timestamp"],
        SourceType.WEATHER: ["timestamp"],
        SourceType.WITNESS: [],
        SourceType.OTHER: [],
    }
    required = required_by_type.get(source_type, [])
    missing = [field_name for field_name in required if not normalized.get(field_name)]
    if missing:
        warnings.append(f"Missing required fields: {', '.join(missing)}")
        return False, warnings
    return True, warnings
