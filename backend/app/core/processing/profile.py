from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.processing.event_rule import EventRule


@dataclass(frozen=True)
class MatchConfig:
    required_any_headers: tuple[str, ...] = ()
    filename_patterns: tuple[str, ...] = ()
    content_hints: tuple[str, ...] = ()
    min_score: float = 0.35


@dataclass(frozen=True)
class ProcessingProfile:
    """Versioned rule pack for one source_type / domain."""

    id: str
    domain: str
    source_types: tuple[str, ...]
    field_map: dict[str, list[str]]
    required_fields: tuple[str, ...] = ()
    entity_fields: tuple[str, ...] = ("train_id", "signal_id", "equipment_id")
    unit_fields: tuple[str, ...] = ("speed", "temperature", "rainfall", "visibility")
    event_rules: tuple[EventRule, ...] = ()
    match: MatchConfig = field(default_factory=MatchConfig)
    version: str = "1.0.0"

    @property
    def primary_source_type(self) -> str:
        return self.source_types[0] if self.source_types else "other"


@dataclass
class ProfileSelection:
    profile: ProcessingProfile
    match_score: float
    match_reasons: list[str] = field(default_factory=list)
    needs_review: bool = False
    declared_source_type: str | None = None
    scored_alternatives: list[dict[str, Any]] = field(default_factory=list)
