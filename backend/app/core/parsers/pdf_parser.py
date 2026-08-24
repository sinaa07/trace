from pathlib import Path

from pypdf import PdfReader

from app.core.config import settings
from app.core.parsers.base import ParseResult


class PdfParser:
    extensions = {".pdf"}
    mime_types = {"application/pdf"}

    def can_parse(self, mime: str | None, ext: str) -> bool:
        return ext.lower() in self.extensions or (mime in self.mime_types if mime else False)

    def parse(self, path: Path) -> ParseResult:
        warnings: list[str] = []
        records: list[dict] = []

        reader = PdfReader(str(path))
        full_text_parts: list[str] = []
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                warnings.append(f"Page {page_num}: no extractable text")
                continue
            full_text_parts.append(text)

        full_text = "\n".join(full_text_parts)
        for idx, line in enumerate(full_text.splitlines()):
            line = line.strip()
            if line:
                records.append({"line_index": idx, "text": line})

        if not records:
            warnings.append("PDF contained no extractable text lines")

        return ParseResult(
            records=records,
            source_metadata_hints={"format": "pdf_text", "page_count": len(reader.pages)},
            warnings=warnings,
            parser_version=settings.parser_version,
        )
