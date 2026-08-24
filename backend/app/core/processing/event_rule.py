from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EventRule:
    """Declarative rule mapping cleaned record fields to a normalized Event."""

    emit: str
    required_fields: tuple[str, ...] = ()
    source_id_field: str | None = None
    entity_id_field: str | None = None
    attribute_map: dict[str, str] = field(default_factory=dict)
