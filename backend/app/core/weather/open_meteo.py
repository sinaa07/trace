"""Open-Meteo weather client (free, no API key required).

Blueprint cost policy: no paid API for core features. Open-Meteo archive +
forecast endpoints supply historical observations for accident-site analysis.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import settings


@dataclass(frozen=True)
class WeatherObservation:
    latitude: float
    longitude: float
    observed_at: str
    ambient_temp_c: float | None
    rainfall_mm_hour: float | None
    wind_speed_kmh: float | None
    wind_gust_kmh: float | None
    cloud_cover_pct: float | None
    visibility_m: float | None
    weather_code: int | None
    provider: str
    provider_url: str
    hourly_window: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def normalized_for_scoring(self) -> dict[str, float | None]:
        """Map provider fields to WeatherRiskScorer inputs."""
        return {
            "ambient_temp_c": self.ambient_temp_c,
            "rainfall_mm_hour": self.rainfall_mm_hour,
            "wind_speed_kmh": self.wind_speed_kmh,
            "visibility_m": self.visibility_m,
            "rail_temp_c": None,
        }


class OpenMeteoClient:
    ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    HOURLY_VARS = (
        "temperature_2m",
        "precipitation",
        "rain",
        "wind_speed_10m",
        "wind_gusts_10m",
        "cloud_cover",
        "weather_code",
    )
    FORECAST_EXTRA_VARS = ("visibility",)

    def __init__(
        self,
        *,
        archive_url: str | None = None,
        forecast_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.archive_url = archive_url or settings.weather_archive_url
        self.forecast_url = forecast_url or settings.weather_forecast_url
        self.timeout_seconds = timeout_seconds or settings.weather_timeout_seconds

    def fetch_at(
        self,
        *,
        latitude: float,
        longitude: float,
        at_time: datetime | None = None,
    ) -> WeatherObservation | dict[str, str]:
        if not settings.weather_enabled:
            return {"error": "Weather service is disabled (WEATHER_ENABLED=false)"}

        target = at_time or datetime.now(timezone.utc)
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)

        use_forecast = target >= datetime.now(timezone.utc) - timedelta(days=7)
        try:
            if use_forecast:
                payload = self._fetch_forecast(latitude, longitude, target)
                provider_url = self.forecast_url
            else:
                payload = self._fetch_archive(latitude, longitude, target)
                provider_url = self.archive_url
        except httpx.HTTPError as exc:
            return {"error": f"Weather provider request failed: {exc}"}
        except ValueError as exc:
            return {"error": str(exc)}

        hourly = payload.get("hourly") or {}
        times: list[str] = hourly.get("time") or []
        if not times:
            return {"error": "Weather provider returned no hourly data"}

        idx = self._closest_hour_index(times, target)
        observed_at = times[idx]

        visibility = self._hourly_value(hourly, "visibility", idx)
        cloud_cover = self._hourly_value(hourly, "cloud_cover", idx)
        estimated_visibility = visibility
        if estimated_visibility is None and cloud_cover is not None:
            # Rough proxy when visibility is unavailable in archive reanalysis.
            estimated_visibility = max(50.0, 10_000.0 * (1.0 - cloud_cover / 100.0))

        precipitation = self._hourly_value(hourly, "precipitation", idx)
        rain = self._hourly_value(hourly, "rain", idx)
        rainfall = precipitation if precipitation is not None else rain

        return WeatherObservation(
            latitude=latitude,
            longitude=longitude,
            observed_at=observed_at,
            ambient_temp_c=self._hourly_value(hourly, "temperature_2m", idx),
            rainfall_mm_hour=rainfall,
            wind_speed_kmh=self._hourly_value(hourly, "wind_speed_10m", idx),
            wind_gust_kmh=self._hourly_value(hourly, "wind_gusts_10m", idx),
            cloud_cover_pct=cloud_cover,
            visibility_m=estimated_visibility,
            weather_code=self._hourly_int(hourly, "weather_code", idx),
            provider="open-meteo",
            provider_url=provider_url,
            hourly_window={
                "requested_at": target.astimezone(timezone.utc).isoformat(),
                "matched_hour": observed_at,
                "timezone": payload.get("timezone"),
                "elevation_m": payload.get("elevation"),
                "visibility_estimated_from_cloud_cover": visibility is None
                and cloud_cover is not None,
            },
        )

    def _fetch_archive(
        self, latitude: float, longitude: float, target: datetime
    ) -> dict[str, Any]:
        day = target.date().isoformat()
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": day,
            "end_date": day,
            "hourly": ",".join(self.HOURLY_VARS),
            "timezone": "UTC",
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(self.archive_url, params=params)
            response.raise_for_status()
            return response.json()

    def _fetch_forecast(
        self, latitude: float, longitude: float, target: datetime
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        past_days = min(7, max(1, (now.date() - target.date()).days + 1))
        hourly = list(self.HOURLY_VARS) + list(self.FORECAST_EXTRA_VARS)
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(hourly),
            "timezone": "UTC",
            "past_days": past_days,
            "forecast_days": 0,
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(self.forecast_url, params=params)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _closest_hour_index(times: list[str], target: datetime) -> int:
        target_utc = target.astimezone(timezone.utc)

        def _parse(ts: str) -> datetime:
            if ts.endswith("Z"):
                ts = ts[:-1] + "+00:00"
            parsed = datetime.fromisoformat(ts)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

        parsed_times = [_parse(t) for t in times]
        return min(
            range(len(parsed_times)),
            key=lambda i: abs((parsed_times[i] - target_utc).total_seconds()),
        )

    @staticmethod
    def _hourly_value(hourly: dict[str, Any], key: str, idx: int) -> float | None:
        series = hourly.get(key)
        if not isinstance(series, list) or idx >= len(series):
            return None
        value = series[idx]
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _hourly_int(hourly: dict[str, Any], key: str, idx: int) -> int | None:
        value = OpenMeteoClient._hourly_value(hourly, key, idx)
        return int(value) if value is not None else None
