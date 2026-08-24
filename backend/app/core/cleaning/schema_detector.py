from pathlib import Path

import yaml

from app.models.enums import SourceType

# Legacy path retained for reference; live maps live in processing/profiles/.
FIELD_MAPS_PATH = Path(__file__).parent / "field_maps" / "default.yaml"


def load_field_maps() -> dict[str, dict[str, list[str]]]:
    with FIELD_MAPS_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {key.lower(): value for key, value in data.items()}


def detect_schema(source_type: SourceType, record: dict) -> dict[str, str]:
    """Legacy helper; prefer DomainProcessor + ProcessingProfile field maps."""
    maps = load_field_maps()
    schema_key = source_type.value.lower()
    field_map = maps.get(schema_key) or maps.get("other", {})

    detected: dict[str, str] = {}
    lower_keys = {k.lower(): k for k in record.keys()}

    for canonical, aliases in field_map.items():
        for alias in aliases:
            if alias.lower() in lower_keys:
                detected[canonical] = lower_keys[alias.lower()]
                break

    return detected
