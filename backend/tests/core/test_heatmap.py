from core.geo import haversine
from core.heatmap import build_grid, score_grid
from core.models import Coordinate, RiskLevel, Route, WeatherSample


def straight_route(
    route_id: str, lat: float, lon_start: float, lon_end: float, n: int = 20
) -> Route:
    geometry = [
        Coordinate(lat=lat, lon=lon_start + (lon_end - lon_start) * i / (n - 1)) for i in range(n)
    ]
    return Route(id=route_id, label=route_id, geometry=geometry, distance_mi=100, duration_s=3600)


# ---- build_grid() ----


def test_grid_point_count_never_exceeds_the_cap():
    # A wide trip (10 degrees of longitude, ~700+ mi) has an elongated
    # bounding box — exactly the shape that used to overshoot the cap
    # before spacing was widened iteratively rather than computed once.
    route = straight_route("r1", lat=40, lon_start=-100, lon_end=-90, n=50)
    # corridor_mi is generous here so it won't filter anything out itself
    grid = build_grid([route], max_points=225, corridor_mi=1000)
    assert len(grid) <= 225


def test_grid_respects_minimum_spacing_floor_on_a_small_trip():
    # A short trip's bounding box plus buffer is tiny, so without a spacing
    # floor the grid would try to cram 225 points into a few square miles.
    route = straight_route("r1", lat=40, lon_start=-90.01, lon_end=-90.00, n=5)
    grid = build_grid([route], buffer_mi=5, max_points=225, min_spacing_deg=0.1)
    # Spacing floor keeps this coarse; nowhere near 225 points.
    assert len(grid) < 50


def test_grid_filters_to_the_corridor():
    route = straight_route("r1", lat=40, lon_start=-100, lon_end=-90, n=50)
    grid = build_grid([route], buffer_mi=60, corridor_mi=40)
    for point in grid:
        nearest = min(haversine(point, p) for p in route.geometry)
        assert nearest <= 40


def test_grid_covers_a_point_well_outside_a_single_route_but_within_buffer():
    # The buffer (30 mi default) should pull in grid points beyond the
    # route's own bounding box, even though corridor filtering (40 mi) then
    # trims most of them back out again.
    route = straight_route("r1", lat=40, lon_start=-100, lon_end=-90, n=50)
    grid = build_grid([route], buffer_mi=30, corridor_mi=200)  # generous corridor
    lats = [p.lat for p in grid]
    assert max(lats) > 40  # grid extends north of the route's own latitude


def test_grid_handles_multiple_routes():
    r1 = straight_route("r1", lat=40.0, lon_start=-100, lon_end=-90, n=30)
    r2 = straight_route("r2", lat=40.5, lon_start=-100, lon_end=-90, n=30)
    grid = build_grid([r1, r2])
    assert len(grid) > 0


# ---- score_grid() ----


def sample(wind: float = 0.0, rain: float = 0.0, snow: float = 0.0) -> WeatherSample:
    return WeatherSample(wind_mph=wind, gust_mph=wind, rain_in_hr=rain, snow_in_hr=snow)


def test_score_grid_shape_is_hours_by_points():
    points = [Coordinate(lat=0, lon=0), Coordinate(lat=0, lon=1), Coordinate(lat=0, lon=2)]
    hourly_weather = [
        [sample(wind=0), sample(wind=0), sample(wind=0)],  # point 0, 3 hours
        [sample(wind=0), sample(wind=0), sample(wind=0)],  # point 1
        [sample(wind=0), sample(wind=0), sample(wind=0)],  # point 2
    ]
    grid = score_grid(points, hourly_weather, load_lb=10_000)
    assert len(grid) == 3  # hours
    assert all(len(row) == 3 for row in grid)  # points per hour


def test_score_grid_classifies_each_point_hour_independently():
    points = [Coordinate(lat=0, lon=0), Coordinate(lat=0, lon=1)]
    hourly_weather = [
        [sample(wind=10), sample(wind=60)],  # point 0: Low at hour 0, No-travel at hour 1
        [sample(wind=30), sample(wind=30)],  # point 1: Moderate both hours
    ]
    grid = score_grid(points, hourly_weather, load_lb=10_000)

    assert grid[0] == [RiskLevel.LOW, RiskLevel.MODERATE]
    assert grid[1] == [RiskLevel.NO_TRAVEL, RiskLevel.MODERATE]


def test_score_grid_empty_input():
    assert score_grid([], [], load_lb=10_000) == []
