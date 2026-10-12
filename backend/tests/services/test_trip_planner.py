from datetime import UTC, datetime

from core.geo import haversine, interpolate
from core.models import Coordinate, Maneuver, Route, WeatherSample
from services.route_alternatives import RouteAlternativesService
from services.trip_planner import TripPlanner, TripPlanRequest, get_cached_plan_context
from services.weather_service import WeatherService

ORIGIN = Coordinate(lat=40.0, lon=-90.0)
DESTINATION = Coordinate(lat=40.0, lon=-80.0)
DEPARTURE = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC)
EMPTY_TRUCK_LB = 35_000


def straight_line_route(
    route_id: str, duration_s: int, lat_offset: float = 0.0, n: int = 21
) -> Route:
    # Endpoints always land exactly on ORIGIN/DESTINATION (the endpoint
    # guardrail requires that); lat_offset instead bows the route through a
    # midpoint peak, so distinct routes still differ geographically (for
    # overlap_ratio and for giving some checkpoints different weather).
    peak = Coordinate(lat=ORIGIN.lat + lat_offset, lon=(ORIGIN.lon + DESTINATION.lon) / 2)
    half = n // 2
    first = [interpolate(ORIGIN, peak, i / half) for i in range(half)]
    second = [interpolate(peak, DESTINATION, i / (n - half - 1)) for i in range(n - half)]
    geometry = first + second
    maneuvers = [Maneuver(time_s=duration_s, begin_shape_index=0, end_shape_index=n - 1)]
    return Route(
        id=route_id,
        label="",
        geometry=geometry,
        distance_mi=haversine(ORIGIN, DESTINATION),
        duration_s=duration_s,
        maneuvers=maneuvers,
    )


class FakeCache:
    def __init__(self):
        self.store = {}

    def get_many(self, keys):
        return {k: self.store[k] for k in keys if k in self.store}

    def set_many(self, mapping, timeout):
        self.store.update(mapping)


class FakeRoutingProvider:
    def __init__(self, alternates=None):
        self.alternates = alternates or []

    def routes(self, origin, destination, *, vehicle, alternates=0, preferences=None, via=None):
        if preferences is not None or via is not None:
            return []  # nothing extra to offer beyond step 1
        return self.alternates


class UniformWeatherProvider:
    def __init__(self, wind=5.0, gust=8.0, rain=0.0, snow=0.0):
        self.sample = WeatherSample(wind_mph=wind, gust_mph=gust, rain_in_hr=rain, snow_in_hr=snow)

    def hourly(self, points, start, hours):
        return {p: [self.sample] * hours for p in points}


def make_planner(routes, weather_provider):
    routing_provider = FakeRoutingProvider(alternates=routes)
    route_alternatives = RouteAlternativesService(routing_provider)
    weather_service = WeatherService(weather_provider, cache=FakeCache())
    cache = FakeCache()
    planner = TripPlanner(route_alternatives, weather_service, EMPTY_TRUCK_LB, cache=cache)
    return planner, cache


def test_three_low_risk_routes_recommend_the_fastest():
    routes = [
        straight_line_route("a", duration_s=7200, lat_offset=0.0),
        straight_line_route("b", duration_s=3600, lat_offset=3.0),  # fastest
        straight_line_route("c", duration_s=5400, lat_offset=-3.0),
    ]
    planner, _ = make_planner(routes, UniformWeatherProvider())
    request = TripPlanRequest(ORIGIN, DESTINATION, DEPARTURE, load_lb=38_000, interval_mi=25)

    result = planner.plan(request)

    assert len(result.routes) == 3
    recommended = next(r for r in result.routes if r.route.id == result.recommended_route_id)
    assert recommended.route.duration_s == 3600
    assert result.warnings == []


def test_rank_matches_duration_order_when_risk_is_tied():
    routes = [
        straight_line_route("a", duration_s=7200, lat_offset=0.0),
        straight_line_route("b", duration_s=3600, lat_offset=3.0),  # fastest -> rank 1
        straight_line_route("c", duration_s=5400, lat_offset=-3.0),  # rank 2
    ]
    planner, _ = make_planner(routes, UniformWeatherProvider())
    request = TripPlanRequest(ORIGIN, DESTINATION, DEPARTURE, load_lb=38_000, interval_mi=25)

    result = planner.plan(request)

    rank_by_duration = {rp.route.duration_s: rp.rank for rp in result.routes}
    assert rank_by_duration == {3600: 1, 5400: 2, 7200: 3}
    recommended = next(r for r in result.routes if r.route.id == result.recommended_route_id)
    assert recommended.rank == 1


def test_recommendation_reason_mentions_drive_time_when_risk_is_tied():
    routes = [
        straight_line_route("a", duration_s=7200, lat_offset=0.0),
        straight_line_route("b", duration_s=3600, lat_offset=3.0),
    ]
    planner, _ = make_planner(routes, UniformWeatherProvider())
    request = TripPlanRequest(ORIGIN, DESTINATION, DEPARTURE, load_lb=38_000, interval_mi=25)

    result = planner.plan(request)

    assert "drive time vs" in result.recommendation_reason
    assert "on the" in result.recommendation_reason


def test_recommendation_reason_describes_the_first_differing_criterion():
    low = straight_line_route("low", duration_s=3600, lat_offset=0.0)
    severe = straight_line_route("severe", duration_s=3600, lat_offset=5.0)

    class VariableWeatherProvider:
        def hourly(self, points, start, hours):
            result = {}
            for p in points:
                if p.lat > 42.0:  # the "severe" route's checkpoints
                    sample = WeatherSample(
                        wind_mph=50.0, gust_mph=55.0, rain_in_hr=0.0, snow_in_hr=0.0
                    )
                else:
                    sample = WeatherSample(
                        wind_mph=5.0, gust_mph=8.0, rain_in_hr=0.0, snow_in_hr=0.0
                    )
                result[p] = [sample] * hours
            return result

    planner, _ = make_planner([low, severe], VariableWeatherProvider())
    # load_lb kept <= 30,000 so wind 50 lands in Severe, not escalated to
    # No Travel by the load rule (see core/risk/rules.py LOAD_RULES).
    request = TripPlanRequest(ORIGIN, DESTINATION, DEPARTURE, load_lb=20_000, interval_mi=25)

    result = planner.plan(request)

    recommended = next(r for r in result.routes if r.route.id == result.recommended_route_id)
    assert recommended.route.label == "Fastest"  # the "low" route — tied duration, first accepted
    assert "severe miles vs" in result.recommendation_reason
    assert "on the Alternate route." in result.recommendation_reason


def test_all_routes_no_travel_adds_the_banner_warning():
    routes = [straight_line_route("a", duration_s=3600)]
    planner, _ = make_planner(routes, UniformWeatherProvider(wind=60.0))  # >= 55 mph -> No Travel
    request = TripPlanRequest(ORIGIN, DESTINATION, DEPARTURE, load_lb=38_000, interval_mi=25)

    result = planner.plan(request)

    assert "Do not travel at this departure time" in result.warnings
    assert result.recommended_route_id  # still ranks and recommends something


def test_fewer_than_three_routes_warning_passes_through():
    routes = [straight_line_route("a", duration_s=3600)]
    planner, _ = make_planner(routes, UniformWeatherProvider())
    request = TripPlanRequest(ORIGIN, DESTINATION, DEPARTURE, load_lb=38_000, interval_mi=25)

    result = planner.plan(request)

    assert any("Only 1 different route" in w for w in result.warnings)


def test_checkpoints_and_arrival_time_are_populated():
    routes = [straight_line_route("a", duration_s=3600)]
    planner, _ = make_planner(routes, UniformWeatherProvider())
    request = TripPlanRequest(ORIGIN, DESTINATION, DEPARTURE, load_lb=38_000, interval_mi=25)

    result = planner.plan(request)

    route_plan = result.routes[0]
    assert len(route_plan.checkpoints) > 0
    assert route_plan.checkpoints[0].eta == DEPARTURE
    assert route_plan.arrival_time == route_plan.checkpoints[-1].eta


def test_plan_id_is_a_short_hex_string():
    routes = [straight_line_route("a", duration_s=3600)]
    planner, _ = make_planner(routes, UniformWeatherProvider())
    request = TripPlanRequest(ORIGIN, DESTINATION, DEPARTURE, load_lb=38_000, interval_mi=25)

    result = planner.plan(request)

    assert len(result.plan_id) == 6
    int(result.plan_id, 16)  # raises ValueError if not hex


def test_plan_context_is_cached_for_the_heatmap_endpoint():
    routes = [straight_line_route("a", duration_s=3600)]
    routing_provider = FakeRoutingProvider(alternates=routes)
    route_alternatives = RouteAlternativesService(routing_provider)
    weather_service = WeatherService(UniformWeatherProvider(), cache=FakeCache())
    shared_cache = FakeCache()
    planner = TripPlanner(route_alternatives, weather_service, EMPTY_TRUCK_LB, cache=shared_cache)
    request = TripPlanRequest(ORIGIN, DESTINATION, DEPARTURE, load_lb=38_000, interval_mi=25)

    result = planner.plan(request)

    context = get_cached_plan_context(shared_cache, result.plan_id)
    assert context is not None
    assert context.departure_time == DEPARTURE
    assert context.load_lb == 38_000
    assert [r.id for r in context.routes] == [rp.route.id for rp in result.routes]


def test_get_cached_plan_context_returns_none_for_unknown_plan_id():
    assert get_cached_plan_context(FakeCache(), "doesnotexist") is None
