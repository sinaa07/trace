import csv
import io
from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.core.parsers.base import ParseResult


def _sanitize_record(row: dict, row_index: int, warnings: list[str]) -> dict:
    clean: dict[str, str | list[str]] = {}
    for key, value in row.items():
        field = str(key) if key is not None else "_extra"
        if field == "_extra":
            warnings.append(f"Row {row_index}: unexpected extra fields stored in _extra")
        if isinstance(value, list):
            clean[field] = value
        elif value is None:
            clean[field] = ""
        else:
            clean[field] = str(value)
    return clean


class CsvParser:
    extensions = {".csv"}
    mime_types = {"text/csv", "application/csv"}

    def can_parse(self, mime: str | None, ext: str) -> bool:
        return ext.lower() in self.extensions or (mime in self.mime_types if mime else False)

    def parse(self, path: Path) -> ParseResult:
        warnings: list[str] = []
        records: list[dict] = []

        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
            for idx, row in df.iterrows():
                record = {str(k): str(v) for k, v in row.to_dict().items()}
                if not any(v.strip() for v in record.values() if v):
                    warnings.append(f"Row {idx}: empty row skipped")
                    continue
                records.append(record)
            hints = {"columns": list(df.columns.astype(str))}
        except Exception:
            content = path.read_text(encoding="utf-8", errors="replace")
            delimiter = "; " if content.count(";") > content.count(",") else ","
            delimiter = delimiter.strip()
            reader = csv.DictReader(
                io.StringIO(content),
                delimiter=delimiter,
                restkey="_extra",
            )
            for idx, row in enumerate(reader):
                if None in row:
                    warnings.append(f"Row {idx}: row has more columns than header")
                records.append(_sanitize_record(row, idx, warnings))
            hints = {"columns": list(records[0].keys()) if records else []}

        return ParseResult(
            records=records,
            source_metadata_hints=hints,
            warnings=warnings,
            parser_version=settings.parser_version,
        )
