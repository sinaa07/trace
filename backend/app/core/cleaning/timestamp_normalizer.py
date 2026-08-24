from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil import parser as date_parser


def normalize_timestamp(
    value: Any,
    timezone_hint: str | None = None,
) -> tuple[str | None, str | None, list[str]]:
    """Return (normalized_iso, original_str, warnings)."""
    warnings: list[str] = []
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None, ["Missing timestamp value"]

    original = str(value)
    try:
        dt = date_parser.parse(original)
    except (ValueError, TypeError) as exc:
        return None, original, [f"Invalid timestamp '{original}': {exc}"]

    if dt.tzinfo is None:
        tz_name = timezone_hint or "UTC"
        try:
            dt = dt.replace(tzinfo=ZoneInfo(tz_name))
        except ZoneInfoNotFoundError:
            dt = dt.replace(tzinfo=timezone.utc)
            warnings.append(f"Unknown timezone '{tz_name}'; defaulted to UTC")
    else:
        dt = dt.astimezone(timezone.utc)

    return dt.isoformat(), original, warnings
