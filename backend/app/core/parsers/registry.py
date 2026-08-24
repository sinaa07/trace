from pathlib import Path

from app.core.parsers.base import ParseResult, UnsupportedFormatError
from app.core.parsers.csv_parser import CsvParser
from app.core.parsers.json_parser import JsonParser
from app.core.parsers.pdf_parser import PdfParser
from app.core.parsers.txt_parser import TxtParser


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers = [CsvParser(), JsonParser(), TxtParser(), PdfParser()]

    def get_parser(self, filename: str, mime: str | None = None):
        ext = Path(filename).suffix.lower()
        for parser in self._parsers:
            if parser.can_parse(mime, ext):
                return parser
        raise UnsupportedFormatError(
            f"No parser available for file '{filename}' (ext={ext}, mime={mime})"
        )

    def parse(self, path: Path, filename: str, mime: str | None = None) -> ParseResult:
        parser = self.get_parser(filename, mime)
        return parser.parse(path)
