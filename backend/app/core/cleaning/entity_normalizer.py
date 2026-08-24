import re
from typing import Any

ENTITY_ALIASES = {
    "train-102": "TRAIN-102",
    "train102": "TRAIN-102",
    "t-102": "TRAIN-102",
    "s42": "SIGNAL-S42",
    "signal-s42": "SIGNAL-S42",
    "signal s42": "SIGNAL-S42",
}


def normalize_entity(value: Any, entity_type: str = "generic") -> tuple[Any, Any | None]:
    if value is None:
        return value, None

    original = str(value).strip()
    if not original:
        return value, None

    key = original.lower().replace("_", "-")
    if key in ENTITY_ALIASES:
        return ENTITY_ALIASES[key], original

    if entity_type == "train_id":
        normalized = original.upper()
        if not normalized.startswith("TRAIN-"):
            match = re.search(r"(\d+)", normalized)
            if match:
                normalized = f"TRAIN-{match.group(1)}"
        if normalized != original:
            return normalized, original
        return normalized, None

    if entity_type == "signal_id":
        normalized = original.upper().replace(" ", "-")
        if not normalized.startswith("SIGNAL-"):
            if normalized.startswith("S"):
                normalized = f"SIGNAL-{normalized}"
        if normalized != original:
            return normalized, original
        return normalized, None

    return original, None
