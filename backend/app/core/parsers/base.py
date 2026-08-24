from dataclasses import dataclass, field


@dataclass
class ParseResult:
    records: list[dict]
    source_metadata_hints: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    parser_version: str = "1.0.0"


class UnsupportedFormatError(Exception):
    pass
