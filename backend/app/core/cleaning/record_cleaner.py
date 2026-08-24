from typing import Any

from app.core.cleaning.record_validator import CleanedRecord
from app.core.processing.cleaner import DomainProcessor
from app.core.processing.registry import ProcessingProfileRegistry
from app.models.enums import SourceType


class RecordCleaner:
    """Backward-compatible wrapper around DomainProcessor + ProcessingProfiles."""

    def __init__(self, registry: ProcessingProfileRegistry | None = None) -> None:
        self.processor = DomainProcessor(registry=registry)

    def clean_records(
        self,
        records: list[dict[str, Any]],
        source_type: SourceType,
        source_metadata: dict[str, Any] | None = None,
        parse_warnings: list[str] | None = None,
        filename: str | None = None,
    ) -> list[CleanedRecord]:
        cleaned, _selection = self.processor.select_and_clean(
            records,
            source_type,
            filename=filename,
            source_metadata=source_metadata,
            parse_warnings=parse_warnings,
        )
        return cleaned

    def clean_record(
        self,
        record: dict[str, Any],
        source_type: SourceType,
        timezone_hint: str | None = None,
        inherited_warnings: list[str] | None = None,
    ) -> CleanedRecord:
        profile = self.processor.registry.get_default_for_source_type(source_type)
        return self.processor.clean_record(
            record,
            profile,
            timezone_hint=timezone_hint,
            inherited_warnings=inherited_warnings,
        )
