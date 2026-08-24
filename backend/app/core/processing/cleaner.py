from __future__ import annotations

from typing import Any

from app.core.cleaning.entity_normalizer import normalize_entity
from app.core.cleaning.record_validator import CleanedRecord
from app.core.cleaning.timestamp_normalizer import normalize_timestamp
from app.core.cleaning.unit_normalizer import normalize_unit
from app.core.processing.profile import ProcessingProfile, ProfileSelection
from app.core.processing.registry import ProcessingProfileRegistry
from app.models.enums import SourceType


class DomainProcessor:
    """Applies a ProcessingProfile's cleaning strategy to raw parsed records."""

    def __init__(self, registry: ProcessingProfileRegistry | None = None) -> None:
        self.registry = registry or ProcessingProfileRegistry()

    def select_and_clean(
        self,
        records: list[dict[str, Any]],
        source_type: SourceType,
        *,
        filename: str | None = None,
        source_metadata: dict[str, Any] | None = None,
        parse_warnings: list[str] | None = None,
    ) -> tuple[list[CleanedRecord], ProfileSelection]:
        selection = self.registry.select(
            source_type,
            filename=filename,
            records=records,
            source_metadata=source_metadata,
        )
        cleaned = self.clean_records(
            records,
            selection.profile,
            source_metadata=source_metadata,
            parse_warnings=parse_warnings,
        )
        return cleaned, selection

    def clean_records(
        self,
        records: list[dict[str, Any]],
        profile: ProcessingProfile,
        source_metadata: dict[str, Any] | None = None,
        parse_warnings: list[str] | None = None,
    ) -> list[CleanedRecord]:
        timezone_hint = (source_metadata or {}).get("timezone")
        return [
            self.clean_record(
                record,
                profile,
                timezone_hint=timezone_hint,
                inherited_warnings=list(parse_warnings or []),
            )
            for record in records
        ]

    def clean_record(
        self,
        record: dict[str, Any],
        profile: ProcessingProfile,
        timezone_hint: str | None = None,
        inherited_warnings: list[str] | None = None,
    ) -> CleanedRecord:
        schema_map = self._detect_schema(profile, record)
        normalized: dict[str, Any] = {}
        provenance: list[dict[str, Any]] = []
        warnings = list(inherited_warnings or [])

        for canonical, source_key in schema_map.items():
            raw_value = record.get(source_key)
            normalized[canonical] = raw_value

            if canonical == "timestamp":
                norm_ts, original, ts_warnings = normalize_timestamp(
                    raw_value, timezone_hint
                )
                warnings.extend(ts_warnings)
                if norm_ts is not None:
                    normalized[canonical] = norm_ts
                    if original != norm_ts:
                        provenance.append(
                            {
                                "field": canonical,
                                "raw": original,
                                "normalized": norm_ts,
                                "transform": "timestamp_to_utc_iso",
                            }
                        )
                else:
                    normalized[canonical] = None

            elif canonical in profile.entity_fields:
                norm_entity, original_entity = normalize_entity(
                    raw_value, entity_type=canonical
                )
                normalized[canonical] = norm_entity
                if original_entity is not None and norm_entity != original_entity:
                    provenance.append(
                        {
                            "field": canonical,
                            "raw": original_entity,
                            "normalized": norm_entity,
                            "transform": "entity_normalization",
                        }
                    )

            elif canonical in profile.unit_fields:
                norm_unit, original_unit, transform = normalize_unit(
                    raw_value, canonical
                )
                normalized[canonical] = norm_unit
                if transform and original_unit is not None and norm_unit != original_unit:
                    provenance.append(
                        {
                            "field": canonical,
                            "raw": original_unit,
                            "normalized": norm_unit,
                            "transform": transform,
                        }
                    )

        for key, value in record.items():
            if key not in schema_map.values() and key not in normalized:
                normalized[key] = value

        is_valid, validation_warnings = self._validate(profile, normalized)
        warnings.extend(validation_warnings)

        return CleanedRecord(
            raw_data=dict(record),
            normalized_data=normalized,
            field_provenance=provenance or None,
            parse_warnings=warnings or None,
            is_valid=is_valid,
        )

    @staticmethod
    def _detect_schema(
        profile: ProcessingProfile, record: dict[str, Any]
    ) -> dict[str, str]:
        detected: dict[str, str] = {}
        lower_keys = {k.lower(): k for k in record.keys()}
        for canonical, aliases in profile.field_map.items():
            for alias in aliases:
                if alias.lower() in lower_keys:
                    detected[canonical] = lower_keys[alias.lower()]
                    break
        return detected

    @staticmethod
    def _validate(
        profile: ProcessingProfile, normalized: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        missing = [f for f in profile.required_fields if not normalized.get(f)]
        if missing:
            return False, [f"Missing required fields: {', '.join(missing)}"]
        return True, []
