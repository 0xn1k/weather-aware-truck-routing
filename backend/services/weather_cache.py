from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from core.models import Coordinate

# Shared by WeatherService and HeatmapService so a checkpoint and a heatmap
# grid point at the same real-world location reuse one cached fetch
# (backend/README.md Section 9: "Rounding to 0.1 deg lets the 3 routes, the
# checkpoints and the heatmap share weather lookups").
CACHE_ROUND_DECIMALS = 1  # ~0.1 degree, ~7 mi
CACHE_TTL_S = 3 * 60 * 60  # 3 hr — forecasts don't change meaningfully minute to
# minute, so a longer TTL means repeat/overlapping trip requests (re-testing,
# Loom retakes) reuse cache instead of re-hitting Open-Meteo's free-tier quota.
# A checkpoint whose ETA falls beyond hour 48 (an unusually long
# continuous-drive trip — rest breaks aren't modeled, top-level README
# Section 12 decision #7) gets hour 48's weather as the closest
# approximation rather than a separate, uncached fetch.
HOURS = 49


class Cache(Protocol):
    def get_many(self, keys: list[str]) -> dict[str, Any]: ...
    def set_many(self, mapping: dict[str, Any], timeout: int) -> None: ...


def round_point(point: Coordinate) -> Coordinate:
    return Coordinate(
        lat=round(point.lat, CACHE_ROUND_DECIMALS), lon=round(point.lon, CACHE_ROUND_DECIMALS)
    )


def cache_key(
    rounded_point: Coordinate, start_hour: datetime, provider_name: str = "unknown"
) -> str:
    # provider_name namespaces the key so flipping WEATHER_PROVIDER at
    # runtime (providers/registry.py's set_weather_provider_name, behind
    # the frontend's header toggle) can never serve stale fake-weather
    # values back as if they were real, or vice versa, within the TTL.
    hour = start_hour.strftime("%Y%m%dT%H")
    return f"weather:{provider_name}:{rounded_point.lat}:{rounded_point.lon}:{hour}"
