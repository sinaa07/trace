"""MCP weather tool — fetch external observations by accident-site coordinates."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from dateutil import parser as date_parser
from sqlalchemy.orm import Session

from app.core.scorers import WeatherRiskScorer
from app.core.weather.coordinates import IncidentCoordinates, resolve_incident_coordinates
from app.core.weather.open_meteo import OpenMeteoClient, WeatherObservation

def _parse_at_time(value:str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = date_parser.parse(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except(TypeError, ValueError):
        return None

def fetch_weather_at_location(
    db: Session | None,
    *,
    case_id: uuid.UUID | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    at_time: str | None = None,
) -> dict[str, Any]:
    """Blueprint MCP tool: retrieve weather at accident coordinates.

    Coordinates may be supplied directly or resolved from case context when
    ``case_id`` and a database session are available.
    """
    parsed_time = _parse_at_time(at_time)
    coords: IncidentCoordinates | dict[str, str]

    if latitude is not None and longitude is not None:
        coords = IncidentCoordinates(
            latitude=latitude,
            longitude=longitude,
            source="request",
            at_time=parsed_time,
        )
    elif db is not None and case_id is not None:
        resolved = resolve_incident_coordinates(
            db,
            case_id,
            latitude=latitude,
            longitude=longitude,
            at_time=parsed_time,
        )
        if isinstance(resolved, dict):
            return resolved
        coords = resolved
    else:
        return {
            "error": (
                "latitude and longitude are required when case context "
                "is not available"
            )
        }

    client = OpenMeteoClient()
    observation = client.fetch_at(
        latitude=coords.latitude,
        longitude=coords.longitude,
        at_time=coords.at_time or parsed_time,
    )
    if isinstance(observation, dict):
        return observation

    score = WeatherRiskScorer().score(**observation.normalized_for_scoring())
    return {
        "coordinates": {
            "latitude": coords.latitude,
            "longitude": coords.longitude,
            "source": coords.source,
            "detail": coords.detail,
        },
        "requested_at": (coords.at_time or parsed_time).isoformat()
        if (coords.at_time or parsed_time)
        else None,
        "observation": observation.to_dict(),
        "risk_assessment": score.to_dict(),
        "provenance": {
            "provider": observation.provider,
            "provider_url": observation.provider_url,
            "fetched_via": "trace_mcp_weather_tool",
        },
    }
