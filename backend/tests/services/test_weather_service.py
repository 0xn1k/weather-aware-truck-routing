from datetime import UTC, datetime, timedelta

from core.models import CheckpointPlan, Coordinate, WeatherSample
from services.weather_cache import CACHE_TTL_S, HOURS
from services.weather_service import WeatherService

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
    def __init__(self, response_by_point=None):
        self.response_by_point = response_by_point or {}
        self.calls: list[dict] = []

    def hourly(self, points, start, hours):
        self.calls.append({"points": list(points), "start": start, "hours": hours})
        return {p: self.response_by_point.get(p, hour_marked_series(hours)) for p in points}


def hour_marked_series(hours=HOURS):
    # wind_mph encodes the hour index, so tests can assert exactly which
    # hour's sample got picked just by reading the resulting weather.
    return [
        WeatherSample(wind_mph=float(h), gust_mph=0, rain_in_hr=0, snow_in_hr=0)
        for h in range(hours)
    ]


def plan(position, eta, mile=0.0, segment=10.0, place=""):
    return CheckpointPlan(
        position=position, mile_marker=mile, segment_miles=segment, eta=eta, place=place
    )


def test_picks_the_hour_nearest_each_checkpoints_eta():
    point = Coordinate(lat=41.9, lon=-87.6)
    plans = {
        "r1": [
            plan(point, DEPARTURE),  # hour 0
            plan(point, DEPARTURE + timedelta(hours=5)),  # hour 5
            plan(point, DEPARTURE + timedelta(hours=5, minutes=40)),  # rounds to hour 6
        ]
    }
    service = WeatherService(FakeWeatherProvider(), cache=FakeCache())

    result = service.attach_weather(plans, DEPARTURE, LOAD_LB)

    winds = [cp.weather.wind_mph for cp in result["r1"]]
    assert winds == [0.0, 5.0, 6.0]


def test_eta_beyond_48_hours_clamps_to_the_last_available_hour():
    point = Coordinate(lat=41.9, lon=-87.6)
    plans = {"r1": [plan(point, DEPARTURE + timedelta(hours=72))]}
    service = WeatherService(FakeWeatherProvider(), cache=FakeCache())

    result = service.attach_weather(plans, DEPARTURE, LOAD_LB)

    assert result["r1"][0].weather.wind_mph == float(HOURS - 1)


def test_dedupes_checkpoints_rounding_to_the_same_cell():
    a = Coordinate(lat=41.901, lon=-87.601)
    b = Coordinate(lat=41.904, lon=-87.603)  # rounds to the same 0.1 deg cell as a
    plans = {"r1": [plan(a, DEPARTURE), plan(b, DEPARTURE)]}
    provider = FakeWeatherProvider()
    service = WeatherService(provider, cache=FakeCache())

    service.attach_weather(plans, DEPARTURE, LOAD_LB)

    assert len(provider.calls) == 1
    assert len(provider.calls[0]["points"]) == 1


def test_dedupe_is_shared_across_routes():
    point = Coordinate(lat=41.9, lon=-87.6)
    plans = {
        "r1": [plan(point, DEPARTURE)],
        "r2": [plan(point, DEPARTURE + timedelta(hours=1))],
    }
    provider = FakeWeatherProvider()
    service = WeatherService(provider, cache=FakeCache())

    service.attach_weather(plans, DEPARTURE, LOAD_LB)

    assert len(provider.calls) == 1
    assert len(provider.calls[0]["points"]) == 1


def test_distinct_locations_are_fetched_together_in_one_call():
    a = Coordinate(lat=41.9, lon=-87.6)
    b = Coordinate(lat=39.7, lon=-104.9)
    plans = {"r1": [plan(a, DEPARTURE), plan(b, DEPARTURE)]}
    provider = FakeWeatherProvider()
    service = WeatherService(provider, cache=FakeCache())

    service.attach_weather(plans, DEPARTURE, LOAD_LB)

    assert len(provider.calls) == 1  # one batched call
    assert len(provider.calls[0]["points"]) == 2  # for both distinct points


def test_cache_hit_avoids_a_provider_call():
    point = Coordinate(lat=41.9, lon=-87.6)
    cache = FakeCache()
    cache.store["weather:unknown:41.9:-87.6:20260101T06"] = hour_marked_series()
    provider = FakeWeatherProvider()
    service = WeatherService(provider, cache=cache)

    result = service.attach_weather({"r1": [plan(point, DEPARTURE)]}, DEPARTURE, LOAD_LB)

    assert provider.calls == []
    assert result["r1"][0].weather.wind_mph == 0.0


def test_cache_miss_result_is_written_back_with_the_ttl():
    point = Coordinate(lat=41.9, lon=-87.6)
    cache = FakeCache()
    service = WeatherService(FakeWeatherProvider(), cache=cache)

    service.attach_weather({"r1": [plan(point, DEPARTURE)]}, DEPARTURE, LOAD_LB)

    assert "weather:unknown:41.9:-87.6:20260101T06" in cache.store
    mapping, timeout = cache.set_many_calls[0]
    assert timeout == CACHE_TTL_S


def test_departure_time_is_truncated_to_the_hour_for_the_cache_key():
    point = Coordinate(lat=41.9, lon=-87.6)
    departure_with_minutes = datetime(2026, 1, 1, 6, 17, 30, tzinfo=UTC)
    cache = FakeCache()
    service = WeatherService(FakeWeatherProvider(), cache=cache)

    service.attach_weather(
        {"r1": [plan(point, departure_with_minutes)]}, departure_with_minutes, LOAD_LB
    )

    assert "weather:unknown:41.9:-87.6:20260101T06" in cache.store


def test_checkpoint_fields_carry_through_from_the_plan():
    point = Coordinate(lat=41.9, lon=-87.6)
    source = plan(point, DEPARTURE, mile=125.5, segment=25.0, place="Davenport")
    service = WeatherService(FakeWeatherProvider(), cache=FakeCache())

    result = service.attach_weather({"r1": [source]}, DEPARTURE, LOAD_LB)

    cp = result["r1"][0]
    assert cp.mile_marker == 125.5
    assert cp.segment_miles == 25.0
    assert cp.place == "Davenport"
    assert cp.eta == DEPARTURE


def test_risk_is_classified_from_the_picked_weather_sample():
    point = Coordinate(lat=41.9, lon=-87.6)
    # Hour 60 would be wind=60 mph (No Travel) if not clamped — force a
    # known, classifiable value at hour 0 instead for a direct check.
    series = [
        WeatherSample(wind_mph=60.0, gust_mph=70.0, rain_in_hr=0.0, snow_in_hr=0.0)
    ] + hour_marked_series(HOURS - 1)
    provider = FakeWeatherProvider(response_by_point={point: series})
    service = WeatherService(provider, cache=FakeCache())

    result = service.attach_weather({"r1": [plan(point, DEPARTURE)]}, DEPARTURE, LOAD_LB)

    assert result["r1"][0].risk.level.name == "NO_TRAVEL"
    assert result["r1"][0].risk.driver == "wind"
