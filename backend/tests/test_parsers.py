from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.core.parsers.registry import ParserRegistry
from app.core.parsers.base import UnsupportedFormatError


@pytest.fixture()
def registry() -> ParserRegistry:
    return ParserRegistry()


def test_csv_parser(test_data_dir: Path, registry: ParserRegistry):
    result = registry.parse(test_data_dir / "signal_log.csv", "signal_log.csv")
    assert len(result.records) == 3
    assert "timestamp" in result.records[0]


def test_json_parser(test_data_dir: Path, registry: ParserRegistry):
    result = registry.parse(test_data_dir / "train_telemetry.json", "train_telemetry.json")
    assert len(result.records) == 2
    assert result.source_metadata_hints.get("timezone") == "Asia/Kolkata"


def test_txt_parser(test_data_dir: Path, registry: ParserRegistry):
    result = registry.parse(
        test_data_dir / "maintenance_report.txt", "maintenance_report.txt"
    )
    assert len(result.records) >= 2


def test_pdf_parser(tmp_path: Path, registry: ParserRegistry):
    pdf_path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with pdf_path.open("wb") as f:
        writer.write(f)

    result = registry.parse(pdf_path, "sample.pdf")
    assert isinstance(result.records, list)


def test_unsupported_format(tmp_path: Path, registry: ParserRegistry):
    bad_file = tmp_path / "data.xyz"
    bad_file.write_text("content")
    with pytest.raises(UnsupportedFormatError):
        registry.parse(bad_file, "data.xyz")
