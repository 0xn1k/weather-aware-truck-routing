from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

import httpx

from core.models import Coordinate, WeatherSample
from providers.errors import ProviderError
from providers.http import DEFAULT_HEADERS

CM_TO_INCH = 2.54
HOURLY_VARS = "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"
RETRY_BACKOFF_S = 0.5


def _friendly_message(exc: httpx.HTTPError | None) -> str:
    # The raw exception (an httpx error str) embeds the full request URL —
    # every lat/lon in the batch, Open-Meteo's own error text — which used
    # to surface verbatim in the API error response and the UI. Rate
    # limiting (429) is common on the free tier under repeated testing, so
    # it gets its own message; everything else gets a generic one. Neither
    # ever includes the request URL.
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        return "Weather service is temporarily rate-limited. Please wait a moment and try again."
    return "Weather service is temporarily unavailable. Please try again shortly."


class OpenMeteoWeatherProvider:
    """Translates Open-Meteo's forecast API into WeatherSample series, one
    per requested point (backend/README.md Section 5.3). No caching, no
    dedup, no picking "the hour nearest a checkpoint's ETA" — that
    orchestration lives in services/weather_service.py (Phase 4)."""

    def __init__(
        self,
        base_url: str = "https://api.open-meteo.com",
        timeout_s: float = 10.0,
        retries: int = 2,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.retries = retries

    def hourly(
        self, points: list[Coordinate], start: datetime, hours: int
    ) -> dict[Coordinate, list[WeatherSample]]:
        if not points:
            return {}
        params = self._build_params(points, start, hours)
        data = self._get(params)
        # Open-Meteo returns one object per location for a multi-point
        # request, but may collapse to a single (unwrapped) object — handle
        # both rather than assuming.
        locations = data if isinstance(data, list) else [data]
        return {
            point: self._parse_location(location, hours)
            for point, location in zip(points, locations)
        }

    def _build_params(
        self, points: list[Coordinate], start: datetime, hours: int
    ) -> dict[str, str]:
        end = start + timedelta(hours=hours - 1)
        return {
            "latitude": ",".join(str(p.lat) for p in points),
            "longitude": ",".join(str(p.lon) for p in points),
            "hourly": HOURLY_VARS,
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "GMT",
            "start_hour": start.strftime("%Y-%m-%dT%H:%M"),
            "end_hour": end.strftime("%Y-%m-%dT%H:%M"),
        }

    def _get(self, params: dict[str, str]) -> Any:
        url = f"{self.base_url}/v1/forecast"
        last_error: httpx.HTTPError | None = None
        for attempt in range(self.retries + 1):
            if attempt > 0:
                # An immediate retry with no delay is close to guaranteed to
                # hit the same rate limit again — give it a moment first.
                time.sleep(RETRY_BACKOFF_S * attempt)
            try:
                response = httpx.get(
                    url, params=params, headers=DEFAULT_HEADERS, timeout=self.timeout_s
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                last_error = exc
        raise ProviderError(_friendly_message(last_error))

    def _parse_location(self, location: dict[str, Any], hours: int) -> list[WeatherSample]:
        hourly = location["hourly"]
        # Read the actual unit from the response rather than assuming
        # precipitation_unit=inch applies uniformly to snowfall too
        # (top-level README.md Section 5.3).
        snow_unit = location.get("hourly_units", {}).get("snowfall", "inch")

        samples = []
        for i in range(hours):
            snow_raw = hourly["snowfall"][i]
            snow = snow_raw / CM_TO_INCH if snow_unit == "cm" else snow_raw
            samples.append(
                WeatherSample(
                    wind_mph=hourly["wind_speed_10m"][i],
                    gust_mph=hourly["wind_gusts_10m"][i],
                    # rain + showers, since Open-Meteo reports them
                    # separately and rain alone misses thunderstorms
                    # (top-level README.md Section 12, decision #4).
                    rain_in_hr=hourly["rain"][i] + hourly["showers"][i],
                    snow_in_hr=snow,
                )
            )
        return samples
