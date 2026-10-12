from __future__ import annotations

import math

from core.geo import haversine, simplify
from core.models import Coordinate, RiskLevel, Route, WeatherSample
from core.risk.classifier import classify

MI_PER_DEG_LAT = 69.0
MI_PER_DEG_LON_AT_EQUATOR = 69.172
# The corridor filter below is O(grid_points x route_points); a raw
# Valhalla polyline can carry thousands of points per route, so this is
# simplified before use — irrelevant precision loss at the 40-mile
# corridor_mi scale, same reasoning as services/route_alternatives.py's
# SIMPLIFY_TOLERANCE_MI (not shared as a constant: this module doesn't
# depend on services/).
SIMPLIFY_TOLERANCE_MI = 0.1


def build_grid(
    routes: list[Route],
    buffer_mi: float = 30.0,
    corridor_mi: float = 40.0,
    max_points: int = 225,
    min_spacing_deg: float = 0.1,
) -> list[Coordinate]:
    """A regular grid over the bounding box of all routes, expanded by
    buffer_mi, capped at ~max_points by widening the spacing, then trimmed
    to only the points within corridor_mi of some route — the "trip
    corridor" (top-level README.md Section 6)."""
    all_points = [
        p for route in routes for p in simplify(route.geometry, SIMPLIFY_TOLERANCE_MI)
    ]
    lats = [p.lat for p in all_points]
    lons = [p.lon for p in all_points]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    center_lat = (min_lat + max_lat) / 2
    lon_mi_per_deg = MI_PER_DEG_LON_AT_EQUATOR * math.cos(math.radians(center_lat))

    min_lat -= buffer_mi / MI_PER_DEG_LAT
    max_lat += buffer_mi / MI_PER_DEG_LAT
    min_lon -= buffer_mi / lon_mi_per_deg
    max_lon += buffer_mi / lon_mi_per_deg

    lat_span = max_lat - min_lat
    lon_span = max_lon - min_lon
    spacing = max(min_spacing_deg, math.sqrt(lat_span * lon_span / max_points))

    n_lat = max(1, math.floor(lat_span / spacing) + 1)
    n_lon = max(1, math.floor(lon_span / spacing) + 1)
    # A single spacing value derived from area alone can still overshoot
    # max_points once each axis is independently floored — most visibly on
    # an elongated bounding box (a long highway trip is far from square).
    # Widen the spacing until the actual integer grid respects the cap; the
    # point budget (it bounds the weather-call budget, README Section 9)
    # takes priority over the spacing floor here.
    while n_lat * n_lon > max_points:
        spacing *= 1.05
        n_lat = max(1, math.floor(lat_span / spacing) + 1)
        n_lon = max(1, math.floor(lon_span / spacing) + 1)

    grid = [
        Coordinate(lat=min_lat + i * spacing, lon=min_lon + j * spacing)
        for i in range(n_lat)
        for j in range(n_lon)
    ]

    return [
        point
        for point in grid
        if any(haversine(point, route_point) <= corridor_mi for route_point in all_points)
    ]


def score_grid(
    points: list[Coordinate],
    hourly_weather: list[list[WeatherSample]],
    load_lb: float,
) -> list[list[RiskLevel]]:
    """Risk level at every grid point, for every forecast hour.
    hourly_weather[point_index][hour] is the already-fetched weather (the
    network call happens in services/heatmap_service.py, Phase 4). Returns
    risk_levels[hour][point_index] — the "49 x N grid" shape the API
    contract and frontend slider expect."""
    n_points = len(points)
    n_hours = len(hourly_weather[0]) if hourly_weather else 0
    return [
        [classify(hourly_weather[point_idx][hour], load_lb).level for point_idx in range(n_points)]
        for hour in range(n_hours)
    ]
