from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from core.geo import simplify
from core.models import Checkpoint, RouteSummary, WeatherSample
from services.heatmap_service import HeatmapGrid
from services.trip_planner import RoutePlan

# A raw Valhalla polyline can carry thousands of points; the route's own
# Route object keeps that full geometry (needed by core.sampling, already
# consumed by the time this serializer runs), but there's no reason to
# ship it all to the browser. frontend/README.md Section 7 already
# documents "~500 points" as what the map expects.
GEOMETRY_SIMPLIFY_TOLERANCE_MI = 0.1


class PlaceInputSerializer(serializers.Serializer):
    lat = serializers.FloatField()
    lon = serializers.FloatField()
    label = serializers.CharField()


class TripPlanRequestSerializer(serializers.Serializer):
    """Matches backend/README.md Section 8's request contract and the
    frontend's form validation (frontend/README.md Section 9.4)."""

    origin = PlaceInputSerializer()
    destination = PlaceInputSerializer()
    departure_time = serializers.DateTimeField()
    load_weight_lb = serializers.FloatField(min_value=1, max_value=80_000)
    interval_miles = serializers.ChoiceField(choices=[10, 25, 50])

    def validate_departure_time(self, value: datetime) -> datetime:
        now = timezone.now()
        if value < now:
            raise serializers.ValidationError("Departure time cannot be in the past.")
        # Simplification: checks the departure itself, not departure + the
        # eventual route duration (unknown until after routing runs) — see
        # top-level README.md Section 12, decision #10.
        if value > now + timedelta(days=16):
            raise serializers.ValidationError(
                "Departure must be within the 16-day forecast window."
            )
        return value


class GeocodePlaceSerializer(serializers.Serializer):
    lat = serializers.FloatField()
    lon = serializers.FloatField()
    label = serializers.CharField()
    context = serializers.CharField()


class CheckpointResponseSerializer(serializers.Serializer):
    mile = serializers.FloatField(source="mile_marker")
    lat = serializers.FloatField(source="position.lat")
    lon = serializers.FloatField(source="position.lon")
    eta = serializers.DateTimeField()
    wind_mph = serializers.FloatField(source="weather.wind_mph")
    gust_mph = serializers.FloatField(source="weather.gust_mph")
    rain_in_hr = serializers.FloatField(source="weather.rain_in_hr")
    snow_in_hr = serializers.FloatField(source="weather.snow_in_hr")
    risk = serializers.SerializerMethodField()
    driver = serializers.CharField(source="risk.driver")
    segment_miles = serializers.FloatField()

    def get_risk(self, checkpoint: Checkpoint) -> str:
        return checkpoint.risk.level.name.lower()


class PeakReadingResponseSerializer(serializers.Serializer):
    """The single checkpoint where one weather factor (wind/rain/snow) was
    highest on the route — independent of which factor actually drove the
    overall risk there (core/models.py PeakReading; core/ranking.py)."""

    value = serializers.FloatField()
    mile = serializers.FloatField(source="checkpoint.mile_marker")
    eta = serializers.DateTimeField(source="checkpoint.eta")


class RouteSummaryResponseSerializer(serializers.Serializer):
    miles_by_level = serializers.SerializerMethodField()
    avg_risk = serializers.FloatField()
    max_level = serializers.SerializerMethodField()
    worst_checkpoint = CheckpointResponseSerializer()
    peak_wind = PeakReadingResponseSerializer()
    peak_rain = PeakReadingResponseSerializer()
    peak_snow = PeakReadingResponseSerializer()

    def get_miles_by_level(self, summary: RouteSummary) -> dict[str, float]:
        return {level.name.lower(): miles for level, miles in summary.miles_by_level.items()}

    def get_max_level(self, summary: RouteSummary) -> str:
        return summary.max_level.name.lower()


class RoutePlanResponseSerializer(serializers.Serializer):
    id = serializers.CharField(source="route.id")
    label = serializers.CharField(source="route.label")
    rank = serializers.IntegerField()
    geometry = serializers.SerializerMethodField()
    distance_mi = serializers.FloatField(source="route.distance_mi")
    duration_s = serializers.IntegerField(source="route.duration_s")
    arrival_time = serializers.DateTimeField()
    summary = RouteSummaryResponseSerializer()
    checkpoints = CheckpointResponseSerializer(many=True)

    def get_geometry(self, route_plan: RoutePlan) -> dict[str, Any]:
        simplified = simplify(route_plan.route.geometry, GEOMETRY_SIMPLIFY_TOLERANCE_MI)
        return {
            "type": "LineString",
            "coordinates": [[p.lon, p.lat] for p in simplified],
        }


class TripPlanResponseSerializer(serializers.Serializer):
    plan_id = serializers.CharField()
    recommended_route_id = serializers.CharField()
    recommendation_reason = serializers.CharField()
    warnings = serializers.ListField(child=serializers.CharField())
    routes = RoutePlanResponseSerializer(many=True)


class HeatmapResponseSerializer(serializers.Serializer):
    """points + a 49 x N risk-level grid (hour-major) + raw weather in the
    same shape for hover tooltips (top-level README.md Section 6)."""

    points = serializers.SerializerMethodField()
    risk_levels = serializers.SerializerMethodField()
    wind_mph = serializers.SerializerMethodField()
    rain_in_hr = serializers.SerializerMethodField()
    snow_in_hr = serializers.SerializerMethodField()

    def get_points(self, grid: HeatmapGrid) -> list[list[float]]:
        return [[p.lat, p.lon] for p in grid.points]

    def get_risk_levels(self, grid: HeatmapGrid) -> list[list[int]]:
        return [[int(level) for level in row] for row in grid.risk_levels]

    def get_wind_mph(self, grid: HeatmapGrid) -> list[list[float]]:
        return self._transpose(grid, lambda s: s.wind_mph)

    def get_rain_in_hr(self, grid: HeatmapGrid) -> list[list[float]]:
        return self._transpose(grid, lambda s: s.rain_in_hr)

    def get_snow_in_hr(self, grid: HeatmapGrid) -> list[list[float]]:
        return self._transpose(grid, lambda s: s.snow_in_hr)

    @staticmethod
    def _transpose(
        grid: HeatmapGrid, value_of: Callable[[WeatherSample], float]
    ) -> list[list[float]]:
        # grid.weather is point-major (weather[point][hour]); flip to
        # hour-major so it lines up with risk_levels for the frontend slider.
        n_hours = len(grid.weather[0]) if grid.weather else 0
        return [
            [value_of(grid.weather[p][h]) for p in range(len(grid.weather))]
            for h in range(n_hours)
        ]
