import re
from pathlib import Path

from app.core.config import settings
from app.core.parsers.base import ParseResult

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>[\d\-T:+\s]+)\s+\[(?P<level>\w+)\]\s+(?P<message>.+)$"
)
KEY_VALUE_PATTERN = re.compile(r"(\w+)=([^\s]+)")


class TxtParser:
    extensions = {".txt", ".log"}
    mime_types = {"text/plain"}

    def can_parse(self, mime: str | None, ext: str) -> bool:
        return ext.lower() in self.extensions or (mime in self.mime_types if mime else False)

    def parse(self, path: Path) -> ParseResult:
        warnings: list[str] = []
        records: list[dict] = []
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

        for idx, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            match = LOG_PATTERN.match(line)
            if match:
                record = match.groupdict()
                kv_matches = KEY_VALUE_PATTERN.findall(record.get("message", ""))
                for key, value in kv_matches:
                    record[key] = value
                records.append(record)
                continue

            if "," in line and "=" not in line:
                parts = [p.strip() for p in line.split(",")]
                if idx == 0 or (len(parts) >= 2 and records):
                    records.append({"line": line, "parts": parts})
                    continue

            records.append({"line": line, "text": line})

        if not records:
            warnings.append("No parseable lines found in text file")

        return ParseResult(
            records=records,
            source_metadata_hints={"format": "line_based"},
            warnings=warnings,
            parser_version=settings.parser_version,
        )
