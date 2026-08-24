import json
from pathlib import Path

from app.core.config import settings
from app.core.parsers.base import ParseResult


class JsonParser:
    extensions = {".json"}
    mime_types = {"application/json"}

    def can_parse(self, mime: str | None, ext: str) -> bool:
        return ext.lower() in self.extensions or (mime in self.mime_types if mime else False)

    def parse(self, path: Path) -> ParseResult:
        warnings: list[str] = []
        data = json.loads(path.read_text(encoding="utf-8"))

        if isinstance(data, list):
            records = [item if isinstance(item, dict) else {"value": item} for item in data]
        elif isinstance(data, dict):
            if "records" in data and isinstance(data["records"], list):
                records = [
                    item if isinstance(item, dict) else {"value": item}
                    for item in data["records"]
                ]
            else:
                records = [data]
        else:
            records = [{"value": data}]
            warnings.append("JSON root is not object or array; wrapped as single record")

        hints: dict = {}
        if isinstance(data, dict):
            for key in ("source_system", "timezone", "device_id"):
                if key in data:
                    hints[key] = data[key]

        return ParseResult(
            records=records,
            source_metadata_hints=hints,
            warnings=warnings,
            parser_version=settings.parser_version,
        )
