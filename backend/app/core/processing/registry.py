from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.core.processing.matcher import score_profile
from app.core.processing.event_rule import EventRule
from app.core.processing.profile import MatchConfig, ProcessingProfile, ProfileSelection
from app.models.enums import SourceType

PROFILES_DIR = Path(__file__).parent / "profiles"


class ProcessingProfileRegistry:
    """Loads versioned ProcessingProfiles and selects one for an upload."""

    def __init__(self, profiles_dir: Path | None = None) -> None:
        self.profiles_dir = profiles_dir or PROFILES_DIR
        self._profiles: dict[str, ProcessingProfile] = {}
        self.reload()

    def reload(self) -> None:
        self._profiles.clear()
        if not self.profiles_dir.exists():
            return
        for path in sorted(self.profiles_dir.glob("*.yaml")):
            profile = self._load_profile(path)
            self._profiles[profile.id] = profile

    def all_profiles(self) -> list[ProcessingProfile]:
        return list(self._profiles.values())

    def get(self, profile_id: str) -> ProcessingProfile | None:
        return self._profiles.get(profile_id)

    def get_default_for_source_type(self, source_type: SourceType | str) -> ProcessingProfile:
        st = source_type.value if isinstance(source_type, SourceType) else source_type
        candidates = [
            p for p in self._profiles.values() if st in p.source_types
        ]
        if not candidates:
            other = [
                p for p in self._profiles.values() if "other" in p.source_types
            ]
            if other:
                return sorted(other, key=lambda p: p.id)[0]
            raise KeyError(f"No processing profile for source_type={st}")
        return sorted(candidates, key=lambda p: p.id)[0]

    def select(
        self,
        source_type: SourceType | str,
        *,
        filename: str | None = None,
        records: list[dict[str, Any]] | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> ProfileSelection:
        declared = source_type.value if isinstance(source_type, SourceType) else source_type
        declared_profile = self.get_default_for_source_type(declared)

        scored: list[tuple[ProcessingProfile, float, list[str]]] = []
        for profile in self._profiles.values():
            score, reasons = score_profile(
                profile,
                filename=filename,
                records=records,
                source_metadata=source_metadata,
            )
            scored.append((profile, score, reasons))

        scored.sort(key=lambda item: item[1], reverse=True)
        best_profile, best_score, best_reasons = scored[0] if scored else (
            declared_profile,
            0.0,
            ["no_profiles_scored"],
        )

        declared_score = next(
            (s for p, s, _ in scored if p.id == declared_profile.id),
            0.0,
        )
        declared_reasons = next(
            (r for p, _, r in scored if p.id == declared_profile.id),
            [],
        )

        alternatives = [
            {"profile_id": p.id, "score": round(s, 4), "reasons": r[:8]}
            for p, s, r in scored[:5]
        ]

        # Declared source_type is authoritative when confidence is close or best is weak.
        min_score = declared_profile.match.min_score
        disagreement = (
            best_profile.primary_source_type != declared
            and best_score >= min_score
            and best_score > declared_score + 0.15
        )

        if disagreement:
            return ProfileSelection(
                profile=declared_profile,
                match_score=round(declared_score, 4),
                match_reasons=declared_reasons
                + [
                    f"declared_override:{declared}",
                    f"best_alternative:{best_profile.id}:{round(best_score, 4)}",
                ],
                needs_review=True,
                declared_source_type=declared,
                scored_alternatives=alternatives,
            )

        needs_review = declared_score < min_score
        reasons = list(declared_reasons)
        if needs_review:
            reasons.append("low_confidence_match")

        return ProfileSelection(
            profile=declared_profile,
            match_score=round(declared_score, 4),
            match_reasons=reasons,
            needs_review=needs_review,
            declared_source_type=declared,
            scored_alternatives=alternatives,
        )

    @staticmethod
    def _load_profile(path: Path) -> ProcessingProfile:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        match_data = data.get("match") or {}
        event_rules = tuple(
            EventRule(
                emit=str(rule["emit"]),
                required_fields=tuple(rule.get("required_fields") or ()),
                source_id_field=rule.get("source_id_field"),
                entity_id_field=rule.get("entity_id_field"),
                attribute_map={
                    str(k): str(v) for k, v in (rule.get("attribute_map") or {}).items()
                },
            )
            for rule in (data.get("event_rules") or [])
        )
        return ProcessingProfile(
            id=data["id"],
            domain=data.get("domain", "other"),
            source_types=tuple(data.get("source_types") or ["other"]),
            field_map={
                str(k): [str(a) for a in (v or [])]
                for k, v in (data.get("field_map") or {}).items()
            },
            required_fields=tuple(data.get("required_fields") or ()),
            entity_fields=tuple(
                data.get("entity_fields")
                or ("train_id", "signal_id", "equipment_id")
            ),
            unit_fields=tuple(
                data.get("unit_fields")
                or ("speed", "temperature", "rainfall", "visibility")
            ),
            event_rules=event_rules,
            match=MatchConfig(
                required_any_headers=tuple(match_data.get("required_any_headers") or ()),
                filename_patterns=tuple(match_data.get("filename_patterns") or ()),
                content_hints=tuple(match_data.get("content_hints") or ()),
                min_score=float(match_data.get("min_score", 0.35)),
            ),
            version=str(data.get("version", "1.0.0")),
        )
