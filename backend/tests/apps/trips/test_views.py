from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache as django_cache
from rest_framework.test import APIClient

import providers.registry as registry
from apps.trips import views
from core.models import (
    Checkpoint,
    Coordinate,
    PeakReading,
    RiskLevel,
    RiskResult,
    Route,
    RouteSummary,
    WeatherSample,
)
from providers.errors import NoRouteError, ProviderError
from services.trip_planner import RoutePlan, TripPlan, cache_plan_context

ORIGIN = {"lat": 41.8781, "lon": -87.6298, "label": "Chicago, IL"}
DESTINATION = {"lat": 39.7392, "lon": -104.9903, "label": "Denver, CO"}


@pytest.fixture(autouse=True)
def clear_cache():
    django_cache.clear()
    yield
    django_cache.clear()


@pytest.fixture(autouse=True)
def _reset_weather_provider_override():
    yield
    registry._weather_provider_override = None


@pytest.fixture
def client():
    return APIClient()


def make_trip_plan(plan_id="abc123"):
    position = Coordinate(lat=41.9, lon=-87.6)
    weather = WeatherSample(wind_mph=10.0, gust_mph=15.0, rain_in_hr=0.0, snow_in_hr=0.0)
    risk = RiskResult(level=RiskLevel.LOW, driver="wind")
    eta = datetime(2026, 1, 1, 7, 0, 0, tzinfo=UTC)
    checkpoint = Checkpoint(
        position=position,
        mile_marker=25.0,
        segment_miles=25.0,
        eta=eta,
        weather=weather,
        risk=risk,
        place="Somewhere",
    )
    route = Route(
        id="r1",
        label="Fastest",
        geometry=[Coordinate(lat=41.8, lon=-87.6), Coordinate(lat=41.9, lon=-87.5)],
        distance_mi=100.0,
        duration_s=3600,
    )
    miles_by_level = {level: 0.0 for level in RiskLevel}
    miles_by_level[RiskLevel.LOW] = 100.0
    summary = RouteSummary(
        miles_by_level=miles_by_level,
        avg_risk=0.0,
        max_level=RiskLevel.LOW,
        worst_checkpoint=checkpoint,
        peak_wind=PeakReading(checkpoint=checkpoint, value=10.0),
        peak_rain=PeakReading(checkpoint=checkpoint, value=0.0),
        peak_snow=PeakReading(checkpoint=checkpoint, value=0.0),
        duration_s=3600,
    )
    route_plan = RoutePlan(
        route=route, checkpoints=[checkpoint], summary=summary, arrival_time=eta, rank=1
    )
    return TripPlan(
        plan_id=plan_id,
        recommended_route_id="r1",
        recommendation_reason="Only one route is available for this trip.",
        warnings=[],
        routes=[route_plan],
    )


class FakePlanner:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def plan(self, request):
        if self.error:
            raise self.error
        return self.result


class FakeHeatmapService:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def build(self, routes, departure_time, load_lb):
        if self.error:
            raise self.error
        return self.result


def valid_plan_body():
    return {
        "origin": ORIGIN,
        "destination": DESTINATION,
        "departure_time": (datetime.now(UTC) + timedelta(hours=6)).isoformat(),
        "load_weight_lb": 38_000,
        "interval_miles": 25,
    }


# ---- health ----


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---- POST /api/trips/plan ----


def test_plan_valid_request_matches_the_contract_shape(client, monkeypatch):
    monkeypatch.setattr(views, "_build_trip_planner", lambda: FakePlanner(result=make_trip_plan()))

    response = client.post("/api/trips/plan", valid_plan_body(), format="json")

    assert response.status_code == 200
    body = response.json()
    assert body["plan_id"] == "abc123"
    assert body["recommended_route_id"] == "r1"
    route = body["routes"][0]
    assert route["id"] == "r1"
    assert route["rank"] == 1
    assert route["geometry"]["type"] == "LineString"
    assert route["geometry"]["coordinates"][0] == [-87.6, 41.8]  # [lon, lat]
    assert route["summary"]["miles_by_level"]["low"] == 100.0
    assert route["summary"]["max_level"] == "low"
    assert route["summary"]["worst_checkpoint"]["mile"] == 25.0
    assert route["summary"]["peak_wind"]["value"] == 10.0
    assert route["summary"]["peak_wind"]["mile"] == 25.0
    checkpoint = route["checkpoints"][0]
    assert checkpoint["mile"] == 25.0
    assert checkpoint["risk"] == "low"
    assert checkpoint["driver"] == "wind"


def test_plan_load_weight_over_limit_returns_400(client):
    body = valid_plan_body()
    body["load_weight_lb"] = 95_000

    response = client.post("/api/trips/plan", body, format="json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert "load_weight_lb" in response.json()["error"]["fields"]


def test_plan_departure_in_the_past_returns_400(client):
    body = valid_plan_body()
    body["departure_time"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()

    response = client.post("/api/trips/plan", body, format="json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_plan_invalid_interval_returns_400(client):
    body = valid_plan_body()
    body["interval_miles"] = 15  # not one of 10/25/50

    response = client.post("/api/trips/plan", body, format="json")

    assert response.status_code == 400


def test_plan_no_route_returns_422(client, monkeypatch):
    monkeypatch.setattr(
        views, "_build_trip_planner", lambda: FakePlanner(error=NoRouteError("no path"))
    )

    response = client.post("/api/trips/plan", valid_plan_body(), format="json")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_route"


def test_plan_provider_error_returns_502(client, monkeypatch):
    monkeypatch.setattr(
        views, "_build_trip_planner", lambda: FakePlanner(error=ProviderError("Stadia is down"))
    )

    response = client.post("/api/trips/plan", valid_plan_body(), format="json")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_error"


# ---- GET /api/trips/{plan_id}/heatmap ----


def test_heatmap_unknown_plan_id_returns_404(client):
    response = client.get("/api/trips/doesnotexist/heatmap")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "plan_not_found"


def test_heatmap_known_plan_id_returns_the_grid(client, monkeypatch):
    route = Route(
        id="r1",
        label="Fastest",
        geometry=[Coordinate(lat=41.8, lon=-87.6), Coordinate(lat=41.9, lon=-87.5)],
        distance_mi=10.0,
        duration_s=600,
    )
    cache_plan_context(
        django_cache, "abc123", [route], datetime(2026, 1, 1, 6, 0, tzinfo=UTC), 38_000
    )

    class FakeGrid:
        points = [Coordinate(lat=41.85, lon=-87.55)]
        risk_levels = [[RiskLevel.LOW]] * 49
        weather = [[WeatherSample(wind_mph=5.0, gust_mph=8.0, rain_in_hr=0.0, snow_in_hr=0.0)] * 49]

    monkeypatch.setattr(
        views, "_build_heatmap_service", lambda: FakeHeatmapService(result=FakeGrid())
    )

    response = client.get("/api/trips/abc123/heatmap")

    assert response.status_code == 200
    body = response.json()
    assert body["points"] == [[41.85, -87.55]]
    assert len(body["risk_levels"]) == 49
    assert body["risk_levels"][0] == [0]  # RiskLevel.LOW == 0
    assert len(body["wind_mph"]) == 49
    assert body["wind_mph"][0] == [5.0]


def test_heatmap_provider_error_returns_502(client, monkeypatch):
    route = Route(
        id="r1",
        label="Fastest",
        geometry=[Coordinate(lat=41.8, lon=-87.6)],
        distance_mi=10.0,
        duration_s=600,
    )
    cache_plan_context(
        django_cache, "abc123", [route], datetime(2026, 1, 1, 6, 0, tzinfo=UTC), 38_000
    )
    monkeypatch.setattr(
        views,
        "_build_heatmap_service",
        lambda: FakeHeatmapService(error=ProviderError("Open-Meteo is down")),
    )

    response = client.get("/api/trips/abc123/heatmap")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_error"


# ---- GET /api/geocode ----


class FakeGeocodingProvider:
    def __init__(self, result=None, error=None):
        self.result = result or []
        self.error = error

    def search(self, query, limit=5):
        if self.error:
            raise self.error
        return self.result


def test_geocode_returns_places(client, monkeypatch):
    from core.models import Place

    places = [
        Place(lat=39.0997, lon=-94.5786, label="Kansas City", context="Missouri, United States")
    ]
    monkeypatch.setattr(
        views, "build_geocoding_provider", lambda: FakeGeocodingProvider(result=places)
    )

    response = client.get("/api/geocode", {"q": "Kansas City"})

    assert response.status_code == 200
    body = response.json()
    assert body[0]["label"] == "Kansas City"
    assert body[0]["context"] == "Missouri, United States"


def test_geocode_blank_query_returns_empty_list(client, monkeypatch):
    called = []
    monkeypatch.setattr(
        views, "build_geocoding_provider", lambda: called.append(True) or FakeGeocodingProvider()
    )

    response = client.get("/api/geocode", {"q": "   "})

    assert response.status_code == 200
    assert response.json() == []
    assert called == []  # provider never constructed for a blank query


def test_geocode_provider_error_returns_502(client, monkeypatch):
    monkeypatch.setattr(
        views,
        "build_geocoding_provider",
        lambda: FakeGeocodingProvider(error=ProviderError("Photon is down")),
    )

    response = client.get("/api/geocode", {"q": "Denver"})

    assert response.status_code == 502


def test_get_weather_provider_returns_the_current_value(client, settings):
    settings.WEATHER_PROVIDER = "open_meteo"

    response = client.get("/api/weather-provider")

    assert response.status_code == 200
    assert response.json() == {"provider": "open_meteo"}


def test_post_weather_provider_switches_it_without_a_restart(client, settings):
    settings.WEATHER_PROVIDER = "open_meteo"

    post_response = client.post("/api/weather-provider", {"provider": "fake"}, format="json")

    assert post_response.status_code == 200
    assert post_response.json() == {"provider": "fake"}
    # A later, unrelated request sees the switch too — it's process-global
    # state (providers/registry.py), not tied to this one request/client.
    assert client.get("/api/weather-provider").json() == {"provider": "fake"}


def test_post_weather_provider_rejects_an_unknown_value(client):
    response = client.post("/api/weather-provider", {"provider": "accuweather"}, format="json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
