from typing import Any


def normalize_unit(value: Any, field: str) -> tuple[Any, Any | None, str | None]:
    if value is None:
        return value, None, None

    original = value
    try:
        numeric = float(str(value).strip())
    except ValueError:
        return value, None, None

    if field in {"speed", "speed_kmh"}:
        return numeric, original, "speed_kmh"
    if field == "speed_ms":
        converted = round(numeric * 3.6, 4)
        return converted, original, "kmh_from_ms"
    if field in {"temperature", "temp", "temp_c"}:
        return numeric, original, "celsius"
    if field in {"rainfall", "rain", "precipitation_mm"}:
        return numeric, original, "mm"
    if field in {"visibility", "visibility_km"}:
        return numeric, original, "km"

    return value, None, None
