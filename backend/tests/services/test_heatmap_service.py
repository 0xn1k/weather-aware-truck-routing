from datetime import UTC, datetime

from core.models import Coordinate, Route, WeatherSample
from services.heatmap_service import HeatmapService
from services.weather_cache import CACHE_TTL_S, HOURS, cache_key, round_point

DEPARTURE = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC)
LOAD_LB = 38_000


class FakeCache:
    def __init__(self):
        self.store: dict[str, list[WeatherSample]] = {}
        self.set_many_calls: list[tuple[dict, int]] = []

    def get_many(self, keys):
        return {k: self.store[k] for k in keys if k in self.store}

    def set_many(self, mapping, timeout):
        self.store.update(mapping)
        self.set_many_calls.append((dict(mapping), timeout))


class FakeWeatherProvider:
    def __init__(self):
        self.calls: list[dict] = []

    def hourly(self, points, start, hours):
        self.calls.append({"points": list(points), "start": start, "hours": hours})
        return {p: hour_marked_series(hours) for p in points}


def hour_marked_series(hours=HOURS):
    return [
        WeatherSample(wind_mph=float(h), gust_mph=0, rain_in_hr=0, snow_in_hr=0)
        for h in range(hours)
    ]


def straight_route(
    route_id: str, lat: float, lon_start: float, lon_end: float, n: int = 20
) -> Route:
    geometry = [
        Coordinate(lat=lat, lon=lon_start + (lon_end - lon_start) * i / (n - 1)) for i in range(n)
    ]
    return Route(id=route_id, label=route_id, geometry=geometry, distance_mi=100, duration_s=3600)


def test_grid_is_scored_for_every_hour_and_point():
    route = straight_route("r1", lat=40.0, lon_start=-95.0, lon_end=-90.0)
    service = HeatmapService(FakeWeatherProvider(), cache=FakeCache())

    grid = service.build([route], DEPARTURE, LOAD_LB)

    assert len(grid.points) > 0
    assert len(grid.risk_levels) == HOURS
    assert all(len(row) == len(grid.points) for row in grid.risk_levels)
    assert len(grid.weather) == len(grid.points)
    assert all(len(series) == HOURS for series in grid.weather)


def test_shares_cache_with_a_checkpoint_at_the_same_rounded_location():
    route = straight_route("r1", lat=40.0, lon_start=-95.0, lon_end=-90.0)
    cache = FakeCache()
    provider = FakeWeatherProvider()
    service = HeatmapService(provider, cache=cache)

    grid = service.build([route], DEPARTURE, LOAD_LB)

    # Pre-seed the cache the way WeatherService would for one of the grid's
    # own points, then rebuild — that point must now come from cache, not
    # a fresh provider call, proving the two services share key format.
    provider.calls.clear()
    seeded_point = grid.points[0]
    cache.store[cache_key(round_point(seeded_point), DEPARTURE)] = hour_marked_series()

    service.build([route], DEPARTURE, LOAD_LB)

    fetched_points = {p for call in provider.calls for p in call["points"]}
    assert round_point(seeded_point) not in {round_point(p) for p in fetched_points}


def test_cache_writes_use_the_shared_ttl():
    route = straight_route("r1", lat=40.0, lon_start=-95.0, lon_end=-90.0)
    cache = FakeCache()
    service = HeatmapService(FakeWeatherProvider(), cache=cache)

    service.build([route], DEPARTURE, LOAD_LB)

    assert cache.set_many_calls
    _, timeout = cache.set_many_calls[0]
    assert timeout == CACHE_TTL_S


def test_weather_grid_rows_align_with_points_for_hover_tooltips():
    route = straight_route("r1", lat=40.0, lon_start=-95.0, lon_end=-90.0)
    service = HeatmapService(FakeWeatherProvider(), cache=FakeCache())

    grid = service.build([route], DEPARTURE, LOAD_LB)

    for point, series in zip(grid.points, grid.weather):
        # hour_marked_series encodes the hour in wind_mph; hour 0 is always 0.
        assert series[0].wind_mph == 0.0
        assert len(series) == HOURS
