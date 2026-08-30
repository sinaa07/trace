"""Resolve accident-site coordinates from case context and evidence."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.services.storage.repositories.case_repo import CaseRepository
from app.services.storage.repositories.evidence_repo import EvidenceRepository


@dataclass(frozen=True)
class IncidentCoordinates:
    latitude: float
    longitude: float
    source: str
    at_time: datetime | None = None
    detail: str | None = None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coords_from_mapping(data: dict[str, Any]) -> tuple[float, float] | None:
    lat = _as_float(
        data.get("latitude")
        or data.get("lat")
        or data.get("Latitude")
    )
    lon = _as_float(
        data.get("longitude")
        or data.get("lon")
        or data.get("lng")
        or data.get("Longitude")
    )
    if lat is None or lon is None:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return lat, lon


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        from dateutil import parser as date_parser

        parsed = date_parser.parse(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def resolve_incident_coordinates(
    db: Session,
    case_id: uuid.UUID,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    at_time: datetime | None = None,
) -> IncidentCoordinates | dict[str, str]:
    """Resolve coordinates for weather lookup.

    Explicit latitude/longitude win; otherwise derive from case location,
    metadata, or GPS-bearing evidence records near incident time.
    """
    if latitude is not None and longitude is not None:
        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            return {"error": "Invalid latitude/longitude range"}
        return IncidentCoordinates(
            latitude=latitude,
            longitude=longitude,
            source="request",
            at_time=at_time,
        )

    cases = CaseRepository(db)
    case = cases.get(case_id)
    if case is None:
        return {"error": "Case not found"}

    incident_time = at_time or case.incident_time
    if incident_time and incident_time.tzinfo is None:
        incident_time = incident_time.replace(tzinfo=timezone.utc)

    if case.location and isinstance(case.location, dict):
        coords = _coords_from_mapping(case.location)
        if coords:
            return IncidentCoordinates(
                latitude=coords[0],
                longitude=coords[1],
                source="case.location",
                at_time=incident_time,
            )

    metadata = case.metadata_ or {}
    if isinstance(metadata, dict):
        for key in ("coordinates", "location", "incident_site"):
            block = metadata.get(key)
            if isinstance(block, dict):
                coords = _coords_from_mapping(block)
                if coords:
                    return IncidentCoordinates(
                        latitude=coords[0],
                        longitude=coords[1],
                        source=f"case.metadata.{key}",
                        at_time=incident_time,
                    )
        coords = _coords_from_mapping(metadata)
        if coords:
            return IncidentCoordinates(
                latitude=coords[0],
                longitude=coords[1],
                source="case.metadata",
                at_time=incident_time,
            )

    gps = _best_gps_from_evidence(
        EvidenceRepository(db),
        case_id,
        incident_time=incident_time,
    )
    if gps:
        return gps

    return {
        "error": (
            "No coordinates available. Provide latitude/longitude or set "
            "case.location {lat, lon} / upload GPS telemetry evidence."
        )
    }


def _best_gps_from_evidence(
    evidence_repo: EvidenceRepository,
    case_id: uuid.UUID,
    *,
    incident_time: datetime | None,
) -> IncidentCoordinates | None:
    candidates: list[tuple[datetime | None, float, float, str]] = []

    for artifact in evidence_repo.list_artifacts_for_case(case_id):
        for record in evidence_repo.list_records_for_evidence(
            artifact.evidence_id, valid_only=True
        ):
            data = record.normalized_data or record.raw_data or {}
            if not isinstance(data, dict):
                continue
            coords = _coords_from_mapping(data)
            if not coords:
                continue
            ts = _parse_dt(data.get("timestamp") or data.get("time"))
            candidates.append(
                (
                    ts,
                    coords[0],
                    coords[1],
                    f"evidence_record:{record.record_id}",
                )
            )

    if not candidates:
        return None

    if incident_time:
        timed = [c for c in candidates if c[0] is not None]
        if timed:
            best = min(
                timed,
                key=lambda c: abs((c[0] - incident_time).total_seconds()),  # type: ignore[operator]
            )
            return IncidentCoordinates(
                latitude=best[1],
                longitude=best[2],
                source=best[3],
                at_time=incident_time,
                detail="closest GPS sample to incident_time",
            )

    last = candidates[-1]
    return IncidentCoordinates(
        latitude=last[1],
        longitude=last[2],
        source=last[3],
        at_time=incident_time,
        detail="latest GPS sample in evidence",
    )
