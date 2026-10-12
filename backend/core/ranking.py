from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from core.models import Checkpoint, PeakReading, RiskLevel, Route, RouteSummary


def summarize(route: Route, checkpoints: list[Checkpoint]) -> RouteSummary:
    """Reduce a route's checkpoints into the totals the route card, ranking
    and details modal all read from (backend/README.md Section 5.5)."""
    miles_by_level: dict[RiskLevel, float] = {level: 0.0 for level in RiskLevel}
    for cp in checkpoints:
        miles_by_level[cp.risk.level] += cp.segment_miles

    total_miles = sum(cp.segment_miles for cp in checkpoints)
    weighted_sum = sum(cp.risk.level * cp.segment_miles for cp in checkpoints)
    avg_risk = weighted_sum / total_miles if total_miles > 0 else 0.0

    return RouteSummary(
        miles_by_level=miles_by_level,
        avg_risk=avg_risk,
        max_level=max(cp.risk.level for cp in checkpoints),
        worst_checkpoint=_worst_checkpoint(checkpoints),
        peak_wind=_peak(checkpoints, lambda cp: cp.weather.wind_mph),
        peak_rain=_peak(checkpoints, lambda cp: cp.weather.rain_in_hr),
        peak_snow=_peak(checkpoints, lambda cp: cp.weather.snow_in_hr),
        duration_s=route.duration_s,
    )


def _worst_checkpoint(checkpoints: list[Checkpoint]) -> Checkpoint:
    # Highest level wins; the earliest (lowest mile_marker) checkpoint wins ties.
    return max(checkpoints, key=lambda cp: (cp.risk.level, -cp.mile_marker))


def _peak(checkpoints: list[Checkpoint], value_of: Callable[[Checkpoint], float]) -> PeakReading:
    cp = max(checkpoints, key=value_of)
    return PeakReading(checkpoint=cp, value=value_of(cp))


@dataclass(frozen=True)
class RankingCriterion:
    name: str
    value: Callable[[RouteSummary], float]


# The brief's tie-break order, in order: fewest No-travel miles, then fewest
# Severe miles, then fewest High miles, then lowest average risk, then
# shortest drive time (backend/README.md Section 5.5). This is the single
# source of truth for both rank()'s sort key and TripPlanner's "why this
# route" sentence (services/trip_planner.py) — both need to agree on what
# the tie-break criteria are and in what order.
RANKING_CRITERIA: list[RankingCriterion] = [
    RankingCriterion("no_travel_miles", lambda s: s.miles_by_level[RiskLevel.NO_TRAVEL]),
    RankingCriterion("severe_miles", lambda s: s.miles_by_level[RiskLevel.SEVERE]),
    RankingCriterion("high_miles", lambda s: s.miles_by_level[RiskLevel.HIGH]),
    RankingCriterion("avg_risk", lambda s: round(s.avg_risk, 2)),
    RankingCriterion("duration_s", lambda s: s.duration_s),
]


def _sort_key(summary: RouteSummary) -> tuple[float, ...]:
    return tuple(criterion.value(summary) for criterion in RANKING_CRITERIA)


def rank(summaries: dict[str, RouteSummary]) -> list[str]:
    """Route ids ordered best (safest) first, per RANKING_CRITERIA above."""
    return sorted(summaries, key=lambda route_id: _sort_key(summaries[route_id]))
