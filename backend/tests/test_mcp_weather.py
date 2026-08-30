"""Tests for MCP weather tool and Open-Meteo client."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.config import settings
from app.core.mcp.tools import EvidenceTools, TOOL_NAMES
from app.core.mcp.weather_tools import fetch_weather_at_location
from app.core.weather.coordinates import resolve_incident_coordinates
from app.core.weather.open_meteo import OpenMeteoClient
from app.models.case import Case


def test_fetch_weather_tool_registered():
    assert "fetch_weather_at_location" in TOOL_NAMES


def test_fetch_weather_requires_coordinates_without_case():
    result = fetch_weather_at_location(None, case_id=None)
    assert "error" in result


def test_fetch_weather_with_explicit_coordinates():
    mock_response = {
        "timezone": "UTC",
        "elevation": 120.0,
        "hourly": {
            "time": ["2024-08-14T04:00", "2024-08-14T05:00"],
            "temperature_2m": [28.5, 27.8],
            "precipitation": [0.0, 2.4],
            "rain": [0.0, 2.4],
            "wind_speed_10m": [12.0, 18.0],
            "wind_gusts_10m": [20.0, 30.0],
            "cloud_cover": [40.0, 85.0],
            "weather_code": [1, 61],
        },
    }

    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_response,
            raise_for_status=lambda: None,
        )
        result = fetch_weather_at_location(
            None,
            latitude=26.5655,
            longitude=80.5150,
            at_time="2024-08-14T04:48:00Z",
        )

    assert "observation" in result
    obs = result["observation"]
    assert obs["ambient_temp_c"] == 27.8
    assert obs["rainfall_mm_hour"] == 2.4
    assert obs["provider"] == "open-meteo"
    assert result["risk_assessment"]["domain"] == "weather"
    assert result["coordinates"]["source"] == "request"


def test_resolve_coordinates_from_case_location(db_session):
    case = Case(
        case_id=uuid.uuid4(),
        title="Kanpur derailment",
        incident_time=datetime(2024, 8, 14, 4, 48, tzinfo=timezone.utc),
        location={"lat": 26.5655, "lon": 80.5150, "track": "T12"},
        metadata_={},
    )
    db_session.add(case)
    db_session.commit()

    resolved = resolve_incident_coordinates(db_session, case.case_id)
    assert resolved.latitude == pytest.approx(26.5655)
    assert resolved.longitude == pytest.approx(80.5150)
    assert resolved.source == "case.location"


def test_evidence_tools_fetch_weather_auto_resolves_case(db_session):
    case = Case(
        case_id=uuid.uuid4(),
        title="Weather MCP case",
        incident_time=datetime(2024, 8, 14, 4, 48, tzinfo=timezone.utc),
        location={"latitude": 26.5655, "longitude": 80.5150},
        metadata_={},
    )
    db_session.add(case)
    db_session.commit()

    mock_response = {
        "timezone": "UTC",
        "hourly": {
            "time": ["2024-08-14T04:00"],
            "temperature_2m": [30.0],
            "precipitation": [0.0],
            "rain": [0.0],
            "wind_speed_10m": [10.0],
            "wind_gusts_10m": [15.0],
            "cloud_cover": [20.0],
            "weather_code": [0],
        },
    }

    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_response,
            raise_for_status=lambda: None,
        )
        tools = EvidenceTools(db_session, case.case_id)
        result = tools.fetch_weather_at_location()

    assert result["coordinates"]["source"] == "case.location"
    assert result["observation"]["ambient_temp_c"] == 30.0


def test_open_meteo_disabled(monkeypatch):
    monkeypatch.setattr(settings, "weather_enabled", False)
    client = OpenMeteoClient()
    result = client.fetch_at(latitude=1.0, longitude=2.0)
    assert result == {"error": "Weather service is disabled (WEATHER_ENABLED=false)"}


def test_open_meteo_http_error():
    client = OpenMeteoClient()

    with patch("httpx.Client.get", side_effect=httpx.ConnectError("offline")):
        result = client.fetch_at(
            latitude=26.5655,
            longitude=80.5150,
            at_time=datetime(2024, 8, 14, 4, 48, tzinfo=timezone.utc),
        )

    assert "error" in result
    assert "offline" in result["error"]
