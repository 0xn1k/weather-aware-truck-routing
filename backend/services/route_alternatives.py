from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace

from core.geo import bearing, interpolate, offset_point, overlap_ratio, point_within, simplify
from core.models import Coordinate, Route, Vehicle
from core.sampling import cumulative_miles
from providers.errors import NoRouteError, ProviderError
from providers.routing.base import RoutePreferences, RoutingProvider

logger = logging.getLogger(__name__)

KM_TO_MI = 0.621371
OVERLAP_THRESHOLD_MI = 1 * KM_TO_MI  # "within 1 km of an accepted route"
OVERLAP_REJECT_RATIO = 0.80
TIME_REJECT_MULTIPLIER = 1.5
DETOUR_SHIFT_FRACTION = 0.12
DETOUR_MIN_SHIFT_MI = 20 * KM_TO_MI
DETOUR_MAX_SHIFT_MI = 80 * KM_TO_MI
# A short trip (one practical corridor, e.g. a 200 mi same-interstate run)
# can genuinely have fewer than 3 routes that clear the normal filters
# above. Per product decision, this app always shows 3 — so once the
# normal pipeline runs out of strategies, a widened detour shift is tried,
# and failing that, the best of what got rejected is used to fill the
# remaining slots rather than leaving a seat empty. NEAR_DUPLICATE_RATIO
# is the only bar a forced fill-in still has to clear: never show the
# literal same path twice, even under this relaxed mode.
NEAR_DUPLICATE_RATIO = 0.95
DETOUR_SHIFT_MULTIPLIERS = (1.0, 2.0)
# A raw Valhalla polyline can carry thousands of raw shape points (one
# every few metres on curves). overlap_ratio() compares every point of a
# candidate against every point of each already-accepted route — left
# unsimplified, that's an O(n*m) blowup that can peg the CPU for minutes
# on a long trip. Simplify immediately on receipt, before any geometry
# math runs, down to roughly the ~500-point target frontend/README.md
# already documents for map rendering.
SIMPLIFY_TOLERANCE_MI = 0.1
# A routing engine snaps the requested lat/lon to the nearest routable
# road, so a route's geometry endpoints are never bit-for-bit equal to the
# request — but a multi-leg response with a dropped leg (the confirmed
# Valhalla bug this guardrail exists for) ends up far more than a road-snap
# away. 1 mile is generous for the former, nowhere close to covering the
# latter.
ENDPOINT_TOLERANCE_MI = 1.0


@dataclass(frozen=True)
class RouteAlternativesResult:
    routes: list[Route]
    warnings: list[str]


@dataclass(frozen=True)
class _Rejected:
    route: Route
    label: str
    reason: str  # "overlap" | "time" — see _fill_from_rejected


class RouteAlternativesService:
    """The 3-route pipeline: Valhalla alternates -> preference variants ->
    a forced detour (widened if still short), filtering near-duplicates/
    slow candidates and labeling survivors by how each was produced
    (backend/README.md Section 5.1). Always returns 3 routes when the
    underlying road network offers that much raw material — see
    NEAR_DUPLICATE_RATIO above for the one rule a forced fill-in still
    has to clear."""

    def __init__(self, routing_provider: RoutingProvider):
        self.routing_provider = routing_provider

    def get_routes(
        self, origin: Coordinate, destination: Coordinate, vehicle: Vehicle
    ) -> RouteAlternativesResult:
        accepted: list[Route] = []
        rejected: list[_Rejected] = []

        # Step 1: Valhalla's own alternates. Never send date_time; our own
        # sampling code computes ETAs from the departure time separately.
        # No time filter here — these are Valhalla's own curated candidates,
        # presumably all reasonable; the overlap filter still applies, since
        # alternates can still be near-duplicates of each other.
        step1 = self.routing_provider.routes(origin, destination, vehicle=vehicle, alternates=2)
        for candidate in step1:
            self._try_accept(
                accepted, rejected, candidate, label="Alternate", fastest=None,
                origin=origin, destination=destination,
            )

        if not accepted:
            if step1 and not rejected:
                # Every step1 candidate existed but was discarded for not
                # actually reaching the requested endpoints — a provider/
                # parsing bug (see ENDPOINT_TOLERANCE_MI), not "no path
                # exists." NoRouteError (422) would mislabel this as the
                # user's fault.
                raise ProviderError(
                    "Routing provider returned no route with endpoints matching "
                    "the requested origin/destination"
                )
            raise NoRouteError("No route found between origin and destination")

        # The fastest route found here is the stable reference used for the
        # rest of the pipeline's time filter and the detour's midpoint —
        # it does not get redefined as more candidates are accepted.
        fastest_reference = min(accepted, key=lambda r: r.duration_s)

        # Step 2: preference variants
        for label, preferences in (
            ("Prefers state roads", RoutePreferences(use_highways=0.2)),
            ("Avoids tolls", RoutePreferences(use_tolls=0.0)),
        ):
            if len(accepted) >= 3:
                break

            def call_with_preferences(
                preferences: RoutePreferences = preferences,
            ) -> list[Route]:
                return self.routing_provider.routes(
                    origin, destination, vehicle=vehicle, preferences=preferences
                )

            self._try_strategy(
                accepted, rejected, fastest_reference, label, call_with_preferences,
                origin=origin, destination=destination,
            )

        # Step 3: forced detour, left side then right — widening the shift
        # if a short trip's normal-sized detour wasn't enough to clear the
        # overlap filter (see DETOUR_SHIFT_MULTIPLIERS above).
        for multiplier in DETOUR_SHIFT_MULTIPLIERS:
            if len(accepted) >= 3:
                break
            for sign in (1, -1):
                if len(accepted) >= 3:
                    break
                via, label = self._detour_point(fastest_reference, sign, multiplier)

                def call_with_via(via: Coordinate = via) -> list[Route]:
                    return self.routing_provider.routes(
                        origin, destination, vehicle=vehicle, via=via
                    )

                self._try_strategy(
                    accepted, rejected, fastest_reference, label, call_with_via,
                    origin=origin, destination=destination,
                )

        if len(accepted) < 3 and rejected:
            self._fill_from_rejected(accepted, rejected)

        warnings = []
        if len(accepted) < 3:
            # Only reachable if the road network itself has no third real
            # path at all (every strategy above produced the same route or
            # none) — an honest warning beats a fabricated route either way.
            noun = "route" if len(accepted) == 1 else "routes"
            warnings.append(f"Only {len(accepted)} different {noun} exist for this trip")

        final_routes = self._assign_ids(self._promote_fastest(accepted))
        return RouteAlternativesResult(routes=final_routes, warnings=warnings)

    def _try_strategy(
        self,
        accepted: list[Route],
        rejected: list[_Rejected],
        fastest: Route,
        label: str,
        call: Callable[[], list[Route]],
        origin: Coordinate,
        destination: Coordinate,
    ) -> None:
        try:
            candidates = call()
        except NoRouteError:
            return  # this particular variant/detour has no path; skip it, not fatal
        for candidate in candidates:
            self._try_accept(
                accepted, rejected, candidate, label=label, fastest=fastest,
                origin=origin, destination=destination,
            )

    def _try_accept(
        self,
        accepted: list[Route],
        rejected: list[_Rejected],
        candidate: Route,
        label: str,
        fastest: Route | None,
        origin: Coordinate,
        destination: Coordinate,
    ) -> None:
        if not _endpoints_match(candidate, origin, destination):
            # Discarded outright, never added to `rejected` — a route that
            # doesn't actually reach the requested points must never be
            # used as a fallback to hit the "always 3" count (see
            # _fill_from_rejected). This is the exact failure mode of the
            # multi-leg Valhalla bug this guardrail was added to catch.
            logger.warning(
                "Discarding %r candidate: geometry runs %s -> %s, requested %s -> %s",
                label,
                candidate.geometry[0] if candidate.geometry else None,
                candidate.geometry[-1] if candidate.geometry else None,
                origin,
                destination,
            )
            return

        # Simplified copies for the overlap comparison ONLY — never stored
        # back onto the Route. A route's `maneuvers` carry shape-index
        # positions into its *original* geometry array; replacing
        # route.geometry here would make those indices stale and break
        # core.sampling.cumulative_seconds() later. See
        # SIMPLIFY_TOLERANCE_MI above for why this matters at all.
        candidate_simplified = simplify(candidate.geometry, SIMPLIFY_TOLERANCE_MI)

        for existing in accepted:
            existing_simplified = simplify(existing.geometry, SIMPLIFY_TOLERANCE_MI)
            ratio = overlap_ratio(candidate_simplified, existing_simplified, OVERLAP_THRESHOLD_MI)
            if ratio > OVERLAP_REJECT_RATIO:
                rejected.append(_Rejected(candidate, label, reason="overlap"))
                return
        time_limit = fastest.duration_s * TIME_REJECT_MULTIPLIER if fastest is not None else None
        if time_limit is not None and candidate.duration_s > time_limit:
            rejected.append(_Rejected(candidate, label, reason="time"))
            return
        accepted.append(replace(candidate, label=label))

    def _fill_from_rejected(self, accepted: list[Route], rejected: list[_Rejected]) -> None:
        # A route rejected only for being slow is still a genuinely
        # different physical path — prefer those over near-duplicates
        # rejected for overlap when forced to fill remaining slots.
        ordered = sorted(rejected, key=lambda r: 0 if r.reason == "time" else 1)
        for item in ordered:
            if len(accepted) >= 3:
                return
            too_similar = any(
                overlap_ratio(
                    simplify(item.route.geometry, SIMPLIFY_TOLERANCE_MI),
                    simplify(existing.geometry, SIMPLIFY_TOLERANCE_MI),
                    OVERLAP_THRESHOLD_MI,
                )
                > NEAR_DUPLICATE_RATIO
                for existing in accepted
            )
            if too_similar:
                continue
            accepted.append(replace(item.route, label=item.label))

    def _detour_point(
        self, fastest: Route, sign: int, shift_multiplier: float = 1.0
    ) -> tuple[Coordinate, str]:
        points = fastest.geometry
        cum_miles = cumulative_miles(points)
        total_mi = cum_miles[-1]
        mid_mi = total_mi / 2

        i = 0
        for idx in range(len(cum_miles) - 1):
            if cum_miles[idx] <= mid_mi <= cum_miles[idx + 1]:
                i = idx
                break
        span = cum_miles[i + 1] - cum_miles[i]
        fraction = (mid_mi - cum_miles[i]) / span if span > 0 else 0.0
        midpoint = interpolate(points[i], points[i + 1], fraction)

        route_bearing = bearing(points[i], points[i + 1])
        shift_bearing = (route_bearing + sign * 90) % 360
        raw_shift_mi = DETOUR_SHIFT_FRACTION * total_mi * shift_multiplier
        shift_mi = min(
            DETOUR_MAX_SHIFT_MI * shift_multiplier, max(DETOUR_MIN_SHIFT_MI, raw_shift_mi)
        )

        via = offset_point(midpoint, shift_bearing, shift_mi)
        return via, f"{_compass_label(shift_bearing)} detour"

    def _promote_fastest(self, accepted: list[Route]) -> list[Route]:
        if not accepted:
            return accepted
        fastest_idx = min(range(len(accepted)), key=lambda i: accepted[i].duration_s)
        result = list(accepted)
        result[fastest_idx] = replace(result[fastest_idx], label="Fastest")
        return result

    def _assign_ids(self, routes: list[Route]) -> list[Route]:
        return [replace(r, id=f"r{i + 1}") for i, r in enumerate(routes)]


def _endpoints_match(candidate: Route, origin: Coordinate, destination: Coordinate) -> bool:
    if not candidate.geometry:
        return False
    return point_within(candidate.geometry[0], origin, ENDPOINT_TOLERANCE_MI) and point_within(
        candidate.geometry[-1], destination, ENDPOINT_TOLERANCE_MI
    )


def _compass_label(bearing_deg: float) -> str:
    bearing_deg %= 360
    if 45 <= bearing_deg < 135:
        return "Eastern"
    if 135 <= bearing_deg < 225:
        return "Southern"
    if 225 <= bearing_deg < 315:
        return "Western"
    return "Northern"
