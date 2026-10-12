from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.heatmap import build_grid, score_grid
from core.models import Coordinate, RiskLevel, Route, WeatherSample
from providers.weather.base import WeatherProvider
from services.weather_cache import CACHE_TTL_S, HOURS, Cache, cache_key, round_point


@dataclass(frozen=True)
class HeatmapGrid:
    points: list[Coordinate]
    risk_levels: list[list[RiskLevel]]  # risk_levels[hour][point_index], hour 0-48
    weather: list[list[WeatherSample]]  # weather[point_index][hour], for hover tooltips


class HeatmapService:
    """Builds the corridor grid and scores it for every hour 0-48
    (backend/README.md Section 6). Shares its weather cache with
    WeatherService — a grid point and a checkpoint at the same rounded
    location reuse one fetch."""

    def __init__(
        self, weather_provider: WeatherProvider, provider_name: str = "unknown", *, cache: Cache
    ):
        self.weather_provider = weather_provider
        self.provider_name = provider_name
        self.cache = cache

    def build(self, routes: list[Route], departure_time: datetime, load_lb: float) -> HeatmapGrid:
        points = build_grid(routes)
        start_hour = departure_time.replace(minute=0, second=0, microsecond=0)

        series_by_point = self._get_or_fetch(points, start_hour)
        weather = [series_by_point[point] for point in points]

        risk_levels = score_grid(points, weather, load_lb)
        return HeatmapGrid(points=points, risk_levels=risk_levels, weather=weather)

    def _get_or_fetch(
        self, points: list[Coordinate], start_hour: datetime
    ) -> dict[Coordinate, list[WeatherSample]]:
        # Grid points from build_grid() aren't pre-rounded like checkpoint
        # positions are, so round them the same way WeatherService does —
        # this is what makes the two services' cache keys actually collide
        # when they cover the same real-world location.
        rounded_points = {round_point(point) for point in points}
        keys_by_point = {
            point: cache_key(point, start_hour, self.provider_name) for point in rounded_points
        }
        cached = self.cache.get_many(list(keys_by_point.values()))

        series_by_rounded: dict[Coordinate, list[WeatherSample]] = {}
        missing_points = []
        for point, key in keys_by_point.items():
            if key in cached:
                series_by_rounded[point] = cached[key]
            else:
                missing_points.append(point)

        if missing_points:
            fetched = self.weather_provider.hourly(missing_points, start_hour, HOURS)
            to_cache = {keys_by_point[point]: series for point, series in fetched.items()}
            self.cache.set_many(to_cache, timeout=CACHE_TTL_S)
            series_by_rounded.update(fetched)

        return {point: series_by_rounded[round_point(point)] for point in points}
