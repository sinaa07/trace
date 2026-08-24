from __future__ import annotations

import fnmatch
from typing import Any

from app.core.processing.profile import ProcessingProfile


def score_profile(
    profile: ProcessingProfile,
    *,
    filename: str | None = None,
    records: list[dict[str, Any]] | None = None,
    source_metadata: dict[str, Any] | None = None,
) -> tuple[float, list[str]]:
    """Score how well a profile matches parsed evidence. Returns (0..1, reasons)."""
    reasons: list[str] = []
    score = 0.0
    records = records or []
    source_metadata = source_metadata or {}

    headers = _collect_headers(records)
    if headers:
        header_score, header_reasons = _score_headers(profile, headers)
        score += 0.55 * header_score
        reasons.extend(header_reasons)
    else:
        reasons.append("no_headers_available")

    if filename:
        fname_score, fname_reasons = _score_filename(profile, filename)
        score += 0.25 * fname_score
        reasons.extend(fname_reasons)

    content_score, content_reasons = _score_content_hints(profile, records)
    score += 0.15 * content_score
    reasons.extend(content_reasons)

    system = str(source_metadata.get("source_system") or "").lower()
    if system:
        for st in profile.source_types:
            if st.replace("_", "") in system.replace("_", "").replace("-", ""):
                score += 0.05
                reasons.append(f"source_system_hint:{system}")
                break

    return min(score, 1.0), reasons


def _collect_headers(records: list[dict[str, Any]]) -> set[str]:
    headers: set[str] = set()
    for record in records[:20]:
        headers.update(str(k).lower() for k in record.keys())
    return headers


def _score_headers(
    profile: ProcessingProfile, headers: set[str]
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if not profile.field_map:
        return 0.0, ["empty_field_map"]

    matched_canonical = 0
    for canonical, aliases in profile.field_map.items():
        alias_set = {a.lower() for a in aliases} | {canonical.lower()}
        if headers & alias_set:
            matched_canonical += 1
            reasons.append(f"header_match:{canonical}")

    field_score = matched_canonical / max(len(profile.field_map), 1)

    required_any = [h.lower() for h in profile.match.required_any_headers]
    if required_any:
        if headers & set(required_any):
            reasons.append("required_any_headers_hit")
            field_score = min(1.0, field_score + 0.15)
        else:
            reasons.append("required_any_headers_miss")
            field_score *= 0.4

    return field_score, reasons


def _score_filename(
    profile: ProcessingProfile, filename: str
) -> tuple[float, list[str]]:
    name = filename.lower()
    patterns = profile.match.filename_patterns
    if not patterns:
        # Soft boost if primary source_type token appears in filename
        token = profile.primary_source_type.replace("_", "")
        if token and token in name.replace("_", "").replace("-", ""):
            return 0.6, [f"filename_contains:{profile.primary_source_type}"]
        return 0.0, []

    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern.lower()):
            return 1.0, [f"filename_pattern:{pattern}"]
    return 0.0, ["filename_no_match"]


def _score_content_hints(
    profile: ProcessingProfile, records: list[dict[str, Any]]
) -> tuple[float, list[str]]:
    hints = [h.upper() for h in profile.match.content_hints]
    if not hints or not records:
        return 0.0, []

    sample_values: set[str] = set()
    for record in records[:30]:
        for value in record.values():
            if value is None:
                continue
            sample_values.add(str(value).strip().upper())

    hits = [h for h in hints if h in sample_values]
    if not hits:
        return 0.0, ["content_hints_miss"]
    return min(1.0, len(hits) / max(len(hints), 1)), [
        f"content_hint:{h}" for h in hits
    ]
