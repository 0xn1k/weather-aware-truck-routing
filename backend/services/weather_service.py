from __future__ import annotations

from datetime import datetime

from django.core.cache import cache as django_cache

from core.models import Checkpoint, CheckpointPlan, Coordinate, WeatherSample
from core.risk.classifier import classify
from providers.weather.base import WeatherProvider
from services.weather_cache import CACHE_TTL_S, HOURS, Cache, cache_key, round_point


class WeatherService:
    """Turns CheckpointPlans (position + timing, no weather — core/sampling.py)
    into real Checkpoints: dedupe locations, read/fill the cache, batch-fetch
    the rest, pick the hour nearest each ETA, classify (backend/README.md
    Section 5.3)."""

    def __init__(
        self,
        weather_provider: WeatherProvider,
        provider_name: str = "unknown",
        cache: Cache = django_cache,
    ):
        self.weather_provider = weather_provider
        self.provider_name = provider_name
        self.cache = cache

    def attach_weather(
        self,
        checkpoint_plans_by_route: dict[str, list[CheckpointPlan]],
        departure_time: datetime,
        load_lb: float,
    ) -> dict[str, list[Checkpoint]]:
        start_hour = departure_time.replace(minute=0, second=0, microsecond=0)

        all_plans = [plan for plans in checkpoint_plans_by_route.values() for plan in plans]
        rounded_points = {round_point(plan.position) for plan in all_plans}
        series_by_point = self._get_or_fetch(rounded_points, start_hour)

        return {
            route_id: [
                self._build_checkpoint(plan, series_by_point, start_hour, load_lb)
                for plan in plans
            ]
            for route_id, plans in checkpoint_plans_by_route.items()
        }

    def _build_checkpoint(
        self,
        plan: CheckpointPlan,
        series_by_point: dict[Coordinate, list[WeatherSample]],
        start_hour: datetime,
        load_lb: float,
    ) -> Checkpoint:
        series = series_by_point[round_point(plan.position)]
        hour_offset = _nearest_hour_offset(plan.eta, start_hour)
        weather = series[hour_offset]
        return Checkpoint(
            position=plan.position,
            mile_marker=plan.mile_marker,
            segment_miles=plan.segment_miles,
            eta=plan.eta,
            weather=weather,
            risk=classify(weather, load_lb),
            place=plan.place,
        )

    def _get_or_fetch(
        self, rounded_points: set[Coordinate], start_hour: datetime
    ) -> dict[Coordinate, list[WeatherSample]]:
        keys_by_point = {
            point: cache_key(point, start_hour, self.provider_name) for point in rounded_points
        }
        cached = self.cache.get_many(list(keys_by_point.values()))

        series_by_point: dict[Coordinate, list[WeatherSample]] = {}
        missing_points = []
        for point, key in keys_by_point.items():
            if key in cached:
                series_by_point[point] = cached[key]
            else:
                missing_points.append(point)

        if missing_points:
            fetched = self.weather_provider.hourly(missing_points, start_hour, HOURS)
            to_cache = {keys_by_point[point]: series for point, series in fetched.items()}
            self.cache.set_many(to_cache, timeout=CACHE_TTL_S)
            series_by_point.update(fetched)

        return series_by_point


def _nearest_hour_offset(eta: datetime, start_hour: datetime) -> int:
    hours = round((eta - start_hour).total_seconds() / 3600)
    return max(0, min(HOURS - 1, hours))
