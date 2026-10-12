from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from django.core.cache import cache as django_cache

from core.geo import point_within
from core.models import Checkpoint, Coordinate, RiskLevel, Route, RouteSummary, Vehicle
from core.ranking import RANKING_CRITERIA, rank, summarize
from core.sampling import sample_checkpoints
from providers.errors import ProviderError
from services.route_alternatives import ENDPOINT_TOLERANCE_MI, RouteAlternativesService
from services.weather_cache import Cache
from services.weather_service import WeatherService

PLAN_CACHE_TTL_S = 60 * 60  # 60 min (backend/README.md Section 9: "Plan + heatmap corridor")


@dataclass(frozen=True)
class TripPlanRequest:
    origin: Coordinate
    destination: Coordinate
    departure_time: datetime  # UTC
    load_lb: float
    interval_mi: float


@dataclass(frozen=True)
class RoutePlan:
    route: Route
    checkpoints: list[Checkpoint]
    summary: RouteSummary
    arrival_time: datetime
    rank: int  # 1 = recommended, matches ranked_ids order from core.ranking.rank()


@dataclass(frozen=True)
class TripPlan:
    plan_id: str
    recommended_route_id: str
    recommendation_reason: str
    warnings: list[str]
    routes: list[RoutePlan]


@dataclass(frozen=True)
class CachedPlanContext:
    """What services/heatmap_service.py (via the Phase 5 heatmap endpoint)
    needs to rebuild the corridor grid for a plan_id without recomputing
    routes — see get_cached_plan_context()."""

    routes: list[Route]
    departure_time: datetime
    load_lb: float


class TripPlanner:
    """Orchestrates one plan request end to end (top-level README.md, "One
    plan request, step by step"): routes -> checkpoints -> weather -> rank."""

    def __init__(
        self,
        route_alternatives: RouteAlternativesService,
        weather_service: WeatherService,
        empty_truck_weight_lb: float,
        cache: Cache = django_cache,
    ):
        self.route_alternatives = route_alternatives
        self.weather_service = weather_service
        self.empty_truck_weight_lb = empty_truck_weight_lb
        self.cache = cache

    def plan(self, request: TripPlanRequest) -> TripPlan:
        vehicle = Vehicle(load_lb=request.load_lb, empty_weight_lb=self.empty_truck_weight_lb)

        alternatives = self.route_alternatives.get_routes(
            request.origin, request.destination, vehicle
        )
        routes = alternatives.routes
        warnings = list(alternatives.warnings)

        # Defense in depth: route_alternatives.py already enforces this
        # per-candidate, but re-verifying here means ANY future bug in that
        # pipeline (or a provider swapped in later) still can't silently
        # serve a route to the wrong place — it fails loudly instead.
        for route in routes:
            if not (
                route.geometry
                and point_within(route.geometry[0], request.origin, ENDPOINT_TOLERANCE_MI)
                and point_within(route.geometry[-1], request.destination, ENDPOINT_TOLERANCE_MI)
            ):
                raise ProviderError(
                    f"Route {route.id} geometry does not match the requested origin/destination"
                )

        checkpoint_plans_by_route = {
            route.id: sample_checkpoints(
                route.geometry, route.maneuvers, request.interval_mi, request.departure_time
            )
            for route in routes
        }
        checkpoints_by_route = self.weather_service.attach_weather(
            checkpoint_plans_by_route, request.departure_time, request.load_lb
        )

        summaries = {route.id: summarize(route, checkpoints_by_route[route.id]) for route in routes}
        labels_by_id = {route.id: route.label for route in routes}

        ranked_ids = rank(summaries)
        recommended_id = ranked_ids[0]
        reason = _recommendation_reason(ranked_ids, summaries, labels_by_id)
        rank_by_id = {route_id: position + 1 for position, route_id in enumerate(ranked_ids)}

        if all(s.miles_by_level[RiskLevel.NO_TRAVEL] > 0 for s in summaries.values()):
            warnings.append("Do not travel at this departure time")

        route_plans = [
            RoutePlan(
                route=route,
                checkpoints=checkpoints_by_route[route.id],
                summary=summaries[route.id],
                arrival_time=checkpoints_by_route[route.id][-1].eta,
                rank=rank_by_id[route.id],
            )
            for route in routes
        ]

        plan_id = uuid.uuid4().hex[:6]
        cache_plan_context(self.cache, plan_id, routes, request.departure_time, request.load_lb)

        return TripPlan(
            plan_id=plan_id,
            recommended_route_id=recommended_id,
            recommendation_reason=reason,
            warnings=warnings,
            routes=route_plans,
        )


def cache_plan_context(
    cache: Cache, plan_id: str, routes: list[Route], departure_time: datetime, load_lb: float
) -> None:
    """Writes what the heatmap endpoint (Phase 5) needs to rebuild the
    corridor grid for plan_id without recomputing routes. Public and
    symmetric with get_cached_plan_context() below — both read and write
    go through the same key format, so neither callers nor tests need to
    know it."""
    context = CachedPlanContext(routes=routes, departure_time=departure_time, load_lb=load_lb)
    cache.set_many({_plan_cache_key(plan_id): context}, timeout=PLAN_CACHE_TTL_S)


def get_cached_plan_context(cache: Cache, plan_id: str) -> CachedPlanContext | None:
    """Used by the heatmap endpoint (Phase 5) to recover a plan's routes
    without re-running the route pipeline."""
    found = cache.get_many([_plan_cache_key(plan_id)])
    result = found.get(_plan_cache_key(plan_id))
    return result if isinstance(result, CachedPlanContext) else None


def _plan_cache_key(plan_id: str) -> str:
    return f"plan:{plan_id}"


def _recommendation_reason(
    ranked_ids: list[str], summaries: dict[str, RouteSummary], labels_by_id: dict[str, str]
) -> str:
    if len(ranked_ids) < 2:
        return "Only one route is available for this trip."

    winner_id, runner_up_id = ranked_ids[0], ranked_ids[1]
    winner, runner_up = summaries[winner_id], summaries[runner_up_id]
    runner_up_label = labels_by_id[runner_up_id]

    for criterion in RANKING_CRITERIA:
        winner_value = criterion.value(winner)
        runner_up_value = criterion.value(runner_up)
        if winner_value != runner_up_value:
            comparison = _describe(criterion.name, winner_value, runner_up_value)
            return f"{comparison} on the {runner_up_label} route."

    return f"Tied with the {runner_up_label} route on every ranking rule; shorter drive time wins."


def _describe(name: str, winner_value: float, runner_up_value: float) -> str:
    if name.endswith("_miles"):
        label = name.replace("_miles", "").replace("_", " ")
        return f"{winner_value:g} {label} miles vs {runner_up_value:g}"
    if name == "avg_risk":
        return f"{winner_value:.2f} average risk vs {runner_up_value:.2f}"
    return f"{_format_duration(winner_value)} drive time vs {_format_duration(runner_up_value)}"


def _format_duration(seconds: float) -> str:
    hours, remainder = divmod(int(seconds), 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"
