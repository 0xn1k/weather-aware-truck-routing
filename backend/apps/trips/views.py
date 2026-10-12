from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trips.serializers import (
    GeocodePlaceSerializer,
    HeatmapResponseSerializer,
    TripPlanRequestSerializer,
    TripPlanResponseSerializer,
)
from core.models import Coordinate
from providers.errors import NoRouteError, ProviderError
from providers.registry import (
    WEATHER_PROVIDER_NAMES,
    build_geocoding_provider,
    build_routing_provider,
    build_weather_provider,
    get_weather_provider_name,
    set_weather_provider_name,
)
from services.heatmap_service import HeatmapService
from services.route_alternatives import RouteAlternativesService
from services.trip_planner import TripPlanner, TripPlanRequest, get_cached_plan_context
from services.weather_service import WeatherService


def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


# Factories, not module-level singletons, so each request gets fresh
# provider instances built from current settings — and so tests can swap
# these for fakes via monkeypatch instead of hitting real providers
# (backend/README.md Section 10: "API | DRF test client with fake providers").
def _build_trip_planner() -> TripPlanner:
    route_alternatives = RouteAlternativesService(build_routing_provider())
    weather_service = WeatherService(build_weather_provider(), get_weather_provider_name())
    return TripPlanner(route_alternatives, weather_service, settings.ASSUMED_EMPTY_TRUCK_LB)


def _build_heatmap_service() -> HeatmapService:
    return HeatmapService(build_weather_provider(), get_weather_provider_name(), cache=cache)


class TripPlanView(APIView):
    def post(self, request: Request) -> Response:
        serializer = TripPlanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return _validation_error(serializer.errors)

        data = serializer.validated_data
        trip_request = TripPlanRequest(
            origin=Coordinate(lat=data["origin"]["lat"], lon=data["origin"]["lon"]),
            destination=Coordinate(lat=data["destination"]["lat"], lon=data["destination"]["lon"]),
            departure_time=data["departure_time"],
            load_lb=data["load_weight_lb"],
            interval_mi=float(data["interval_miles"]),
        )

        try:
            plan = _build_trip_planner().plan(trip_request)
        except NoRouteError as exc:
            return _error_response("no_route", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY)
        except ProviderError as exc:
            return _error_response("provider_error", str(exc), status.HTTP_502_BAD_GATEWAY)

        return Response(TripPlanResponseSerializer(plan).data)


class HeatmapView(APIView):
    def get(self, request: Request, plan_id: str) -> Response:
        context = get_cached_plan_context(cache, plan_id)
        if context is None:
            return _error_response(
                "plan_not_found",
                "This plan has expired or does not exist. Submit a new plan request.",
                status.HTTP_404_NOT_FOUND,
            )

        try:
            grid = _build_heatmap_service().build(
                context.routes, context.departure_time, context.load_lb
            )
        except ProviderError as exc:
            return _error_response("provider_error", str(exc), status.HTTP_502_BAD_GATEWAY)

        return Response(HeatmapResponseSerializer(grid).data)


class WeatherProviderView(APIView):
    """Lets the frontend's header toggle switch between live weather
    (open_meteo) and the deterministic dummy weather (fake,
    providers/weather/fake.py) without an env var change + redeploy —
    see providers/registry.py's set_weather_provider_name for exactly what
    this does and does not affect. Deliberately unauthenticated: this app
    has no auth system anywhere, and the toggle is meant to be flippable
    from the deployed site itself. That's fine for a single-person demo
    deployment; don't expose this unauthenticated on a real multi-tenant
    service."""

    def get(self, request: Request) -> Response:
        return Response({"provider": get_weather_provider_name()})

    def post(self, request: Request) -> Response:
        provider = request.data.get("provider")
        if provider not in WEATHER_PROVIDER_NAMES:
            return _validation_error(
                {"provider": [f"Must be one of {WEATHER_PROVIDER_NAMES}."]}
            )
        set_weather_provider_name(provider)
        return Response({"provider": provider})


class GeocodeView(APIView):
    def get(self, request: Request) -> Response:
        query = request.query_params.get("q", "")
        if not query.strip():
            return Response([])

        try:
            places = build_geocoding_provider().search(query)
        except ProviderError as exc:
            return _error_response("provider_error", str(exc), status.HTTP_502_BAD_GATEWAY)

        return Response(GeocodePlaceSerializer(places, many=True).data)


def _validation_error(errors: dict[str, Any]) -> Response:
    return _error_response(
        "validation_error", "Invalid input.", status.HTTP_400_BAD_REQUEST, fields=errors
    )


def _error_response(
    code: str, message: str, http_status: int, fields: dict[str, Any] | None = None
) -> Response:
    return Response(
        {"error": {"code": code, "message": message, "fields": fields or {}}},
        status=http_status,
    )
