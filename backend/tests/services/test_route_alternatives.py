import pytest

from core.geo import interpolate
from core.models import Coordinate, Maneuver, Route, Vehicle
from providers.errors import NoRouteError, ProviderError
from services.route_alternatives import RouteAlternativesService

ORIGIN = Coordinate(lat=40.0, lon=-90.0)
DESTINATION = Coordinate(lat=40.0, lon=-80.0)
VEHICLE = Vehicle(load_lb=38_000, empty_weight_lb=35_000)


def make_route(route_id: str, duration_s: int, lon_offset: float = 0.0) -> Route:
    # Endpoints always land exactly on ORIGIN/DESTINATION (the endpoint
    # guardrail requires that); lon_offset instead bows a middle point
    # north/south so overlap_ratio still sees distinct routes — a tiny
    # offset keeps the bowed point a near-duplicate of the unbowed one.
    geometry = [
        ORIGIN,
        Coordinate(lat=40.0 + lon_offset, lon=-85.0),
        DESTINATION,
    ]
    return Route(id=route_id, label="", geometry=geometry, distance_mi=530, duration_s=duration_s)


class FakeRoutingProvider:
    def __init__(
        self, alternates=None, alternates_error=None, preference_results=None, via_results=None
    ):
        self.alternates = alternates or []
        self.alternates_error = alternates_error
        self.preference_results = preference_results or {}  # {(use_highways, use_tolls): [Route]}
        self.via_results = list(via_results or [])  # consumed in order
        self.calls: list[dict] = []

    def routes(self, origin, destination, *, vehicle, alternates=0, preferences=None, via=None):
        self.calls.append(
            {
                "alternates": alternates,
                "preferences": preferences,
                "via": via,
            }
        )
        if via is not None:
            return self.via_results.pop(0) if self.via_results else []
        if preferences is not None:
            key = (preferences.use_highways, preferences.use_tolls)
            return self.preference_results.get(key, [])
        if self.alternates_error:
            raise self.alternates_error
        return self.alternates


# ---- step 1 alone ----


def test_three_distinct_alternates_need_nothing_else():
    provider = FakeRoutingProvider(
        alternates=[
            make_route("a", duration_s=1000, lon_offset=0.0),
            make_route("b", duration_s=1500, lon_offset=5.0),
            make_route("c", duration_s=2000, lon_offset=-5.0),
        ]
    )
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    assert len(result.routes) == 3
    assert result.warnings == []
    # Only the single alternates call should have happened — no preference
    # or detour calls needed once 3 distinct routes are already found.
    assert len(provider.calls) == 1


def test_fastest_route_is_labeled_fastest_others_alternate():
    provider = FakeRoutingProvider(
        alternates=[
            make_route("a", duration_s=2000, lon_offset=0.0),
            make_route("b", duration_s=1000, lon_offset=5.0),  # this one is fastest
            make_route("c", duration_s=1500, lon_offset=-5.0),
        ]
    )
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    labels = {r.duration_s: r.label for r in result.routes}
    assert labels[1000] == "Fastest"
    assert labels[2000] == "Alternate"
    assert labels[1500] == "Alternate"


def test_near_duplicate_alternates_are_filtered_by_overlap():
    provider = FakeRoutingProvider(
        alternates=[
            make_route("a", duration_s=1000, lon_offset=0.0),
            make_route("b", duration_s=1010, lon_offset=0.0001),  # near-identical to a
        ],
        preference_results={},
        via_results=[[], []],  # nothing found on either detour side either
    )
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    assert len(result.routes) == 1
    assert "Only 1 different route" in result.warnings[0]


def test_accepted_routes_keep_their_original_geometry_and_maneuvers():
    # A dense, perfectly straight 500-point route — simplify() would
    # collapse this to 2 points. The ACCEPTED route must still carry all
    # 500, with maneuvers untouched, or core.sampling's shape-index-based
    # ETA calculation breaks downstream (services/route_alternatives.py
    # simplifies only a local copy for the overlap check, never the
    # stored Route — see SIMPLIFY_TOLERANCE_MI's comment there).
    n = 500
    dense_geometry = [interpolate(ORIGIN, DESTINATION, i / (n - 1)) for i in range(n)]
    maneuvers = [Maneuver(time_s=1000, begin_shape_index=0, end_shape_index=n - 1)]
    dense_route = Route(
        id="dense",
        label="",
        geometry=dense_geometry,
        distance_mi=530,
        duration_s=1000,
        maneuvers=maneuvers,
    )
    provider = FakeRoutingProvider(alternates=[dense_route])
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    assert len(result.routes) == 1
    accepted = result.routes[0]
    assert len(accepted.geometry) == n
    assert accepted.maneuvers == maneuvers


def test_overlap_check_still_rejects_near_duplicates_when_geometry_is_dense():
    n = 500
    route_a_geometry = [interpolate(ORIGIN, DESTINATION, i / (n - 1)) for i in range(n)]
    nudged = Coordinate(lat=ORIGIN.lat + 0.0001, lon=ORIGIN.lon)
    route_b_geometry = [interpolate(nudged, DESTINATION, i / (n - 1)) for i in range(n)]
    provider = FakeRoutingProvider(
        alternates=[
            Route(id="a", label="", geometry=route_a_geometry, distance_mi=530, duration_s=1000),
            Route(id="b", label="", geometry=route_b_geometry, distance_mi=530, duration_s=1010),
        ],
        via_results=[[], []],
    )
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    assert len(result.routes) == 1  # b still correctly detected as a near-duplicate of a


def test_step1_skips_the_time_filter():
    # An alternate that's far more than 1.5x the eventual-fastest's time is
    # still accepted when it comes from step 1 — only step 2/3 candidates
    # are time-filtered against the fastest reference.
    provider = FakeRoutingProvider(
        alternates=[
            make_route("a", duration_s=1000, lon_offset=0.0),
            make_route("b", duration_s=5000, lon_offset=5.0),  # 5x the fastest
        ]
    )
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    assert len(result.routes) == 2


# ---- step 2: preference variants ----


def test_preference_variant_fills_in_a_missing_route_with_its_own_label():
    provider = FakeRoutingProvider(
        alternates=[make_route("a", duration_s=1000, lon_offset=0.0)],
        preference_results={
            (0.2, None): [make_route("hw", duration_s=1100, lon_offset=5.0)],
            (None, 0.0): [make_route("toll", duration_s=1200, lon_offset=-5.0)],
        },
    )
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    labels = {r.duration_s: r.label for r in result.routes}
    assert labels[1100] == "Prefers state roads"
    assert labels[1200] == "Avoids tolls"
    assert len(result.routes) == 3


def test_time_rejected_candidate_still_used_as_fallback_when_short_of_three():
    # "hw" is > 1.5x the fastest route's time, so it's excluded from the
    # normal 3 — but it's a genuinely different physical path (far apart
    # geographically), not a near-duplicate. Product decision: the app
    # always shows 3 routes when the road network offers that much raw
    # material, so a merely-slow-but-distinct candidate gets used to fill
    # the remaining slot rather than leaving the trip at 1 route.
    provider = FakeRoutingProvider(
        alternates=[make_route("a", duration_s=1000, lon_offset=0.0)],
        preference_results={
            (0.2, None): [make_route("hw", duration_s=1000 * 1.6, lon_offset=5.0)],  # > 1.5x
        },
        via_results=[[], [], [], []],
    )
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    assert len(result.routes) == 2
    assert any(r.label == "Prefers state roads" for r in result.routes)
    # Still short of 3 — only one fallback candidate existed — so the
    # honest warning correctly still fires; "always 3" never means "fake
    # a count that wasn't actually reached."
    assert "Only 2 different routes" in result.warnings[0]


def test_preference_variant_no_route_is_skipped_not_fatal():
    provider = FakeRoutingProvider(
        alternates=[make_route("a", duration_s=1000, lon_offset=0.0)],
        preference_results={},  # neither variant returns anything (empty, not an error)
        via_results=[
            [make_route("d1", duration_s=1100, lon_offset=8.0)],
            [],
        ],
    )
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    assert len(result.routes) == 2  # step1's route + the detour route


# ---- step 3: detour ----


def test_detour_label_matches_the_perpendicular_compass_direction():
    # The fastest route runs due east (bearing 90). Shifting +90 from that
    # gives bearing 180 = due south -> "Southern detour".
    provider = FakeRoutingProvider(
        alternates=[make_route("a", duration_s=1000, lon_offset=0.0)],
        preference_results={},
        via_results=[[make_route("d", duration_s=1050, lon_offset=10.0)]],
    )
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    detour = next(r for r in result.routes if r.duration_s == 1050)
    assert detour.label == "Southern detour"


def test_detour_via_point_is_passed_to_the_provider():
    # Two routes from step 1 + one successful left-side detour already
    # makes 3, so the service stops before trying the right side — exactly
    # one via-call.
    provider = FakeRoutingProvider(
        alternates=[
            make_route("a", duration_s=1000, lon_offset=0.0),
            make_route("b", duration_s=1100, lon_offset=5.0),
        ],
        preference_results={},
        via_results=[[make_route("d", duration_s=1050, lon_offset=10.0)]],
    )
    service = RouteAlternativesService(provider)

    service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    via_calls = [c for c in provider.calls if c["via"] is not None]
    assert len(via_calls) == 1
    assert isinstance(via_calls[0]["via"], Coordinate)


# ---- always-3 fallback (product decision: never leave a trip at < 3
# routes when the road network has more real paths to offer, even if that
# means widening the detour shift or reusing a merely-slow candidate) ----


def test_widens_the_detour_when_the_normal_sized_one_finds_nothing():
    # The normal-sized detour (multiplier 1.0, both sides) comes back
    # empty — realistic for a short trip with one practical corridor.
    # Only the widened attempt (multiplier 2.0) finds real paths.
    provider = FakeRoutingProvider(
        alternates=[make_route("a", duration_s=1000, lon_offset=0.0)],
        preference_results={},
        via_results=[
            [],  # multiplier 1.0, left
            [],  # multiplier 1.0, right
            [make_route("b", duration_s=1100, lon_offset=5.0)],  # multiplier 2.0, left
            [make_route("c", duration_s=1150, lon_offset=-5.0)],  # multiplier 2.0, right
        ],
    )
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    assert len(result.routes) == 3
    assert result.warnings == []
    via_calls = [c for c in provider.calls if c["via"] is not None]
    assert len(via_calls) == 4  # tried all 4 before giving up


def test_warning_only_appears_when_truly_no_third_path_exists():
    # Nothing anywhere — step 1 gives 1 route, every other strategy and
    # every detour width returns empty. No candidate ever existed to fall
    # back to, so the honest warning is the only correct outcome.
    provider = FakeRoutingProvider(
        alternates=[make_route("a", duration_s=1000, lon_offset=0.0)],
        preference_results={},
        via_results=[[], [], [], []],
    )
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    assert len(result.routes) == 1
    assert "Only 1 different route" in result.warnings[0]


# ---- ids, no-route propagation ----


def test_ids_are_assigned_sequentially_regardless_of_provider_ids():
    provider = FakeRoutingProvider(
        alternates=[
            make_route("whatever-1", duration_s=1000, lon_offset=0.0),
            make_route("whatever-2", duration_s=1100, lon_offset=5.0),
        ]
    )
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    assert [r.id for r in result.routes] == ["r1", "r2"]


def test_no_route_in_step1_propagates_immediately():
    provider = FakeRoutingProvider(alternates_error=NoRouteError("no path"))
    service = RouteAlternativesService(provider)

    with pytest.raises(NoRouteError):
        service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    # Nothing beyond the one failing alternates call should have been tried.
    assert len(provider.calls) == 1


# ---- endpoint guardrail: every accepted route must actually start/end at
# the requested origin/destination (regression coverage for the multi-leg
# Valhalla bug that silently dropped a detour route's final leg) ----


def make_route_with_endpoints(route_id, duration_s, start, end):
    geometry = [start, Coordinate(lat=40.0, lon=-85.0), end]
    return Route(id=route_id, label="", geometry=geometry, distance_mi=530, duration_s=duration_s)


WRONG_END = Coordinate(lat=38.0, lon=-90.0)  # nowhere near DESTINATION


def test_candidate_with_wrong_end_point_is_discarded_not_accepted():
    provider = FakeRoutingProvider(
        alternates=[
            make_route("a", duration_s=1000, lon_offset=0.0),
            make_route_with_endpoints("bad", duration_s=1010, start=ORIGIN, end=WRONG_END),
        ],
        via_results=[[], []],
    )
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    assert [r.id for r in result.routes] == ["r1"]
    assert "Only 1 different route" in result.warnings[0]


def test_candidate_with_wrong_end_point_is_never_used_as_a_fallback():
    # "bad" is the only other candidate available anywhere in the pipeline
    # — if it were used as a fallback to hit the "always 3" count, that
    # would recreate exactly the bug this guardrail exists to prevent.
    provider = FakeRoutingProvider(
        alternates=[make_route("a", duration_s=1000, lon_offset=0.0)],
        preference_results={
            (0.2, None): [
                make_route_with_endpoints("bad", duration_s=1600, start=ORIGIN, end=WRONG_END)
            ],
        },
        via_results=[[], [], [], []],
    )
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    assert [r.id for r in result.routes] == ["r1"]
    assert "Only 1 different route" in result.warnings[0]


def test_a_route_snapped_slightly_off_the_exact_request_point_is_still_accepted():
    # A routing engine snaps the requested lat/lon to the nearest routable
    # road — a few hundred metres off is normal, not a bug.
    snapped_origin = Coordinate(lat=ORIGIN.lat + 0.005, lon=ORIGIN.lon)  # ~0.35 mi
    provider = FakeRoutingProvider(
        alternates=[
            make_route_with_endpoints("a", duration_s=1000, start=snapped_origin, end=DESTINATION)
        ]
    )
    service = RouteAlternativesService(provider)

    result = service.get_routes(ORIGIN, DESTINATION, VEHICLE)

    assert len(result.routes) == 1


def test_all_step1_candidates_with_bad_endpoints_raises_provider_error():
    provider = FakeRoutingProvider(
        alternates=[
            make_route_with_endpoints("bad1", duration_s=1000, start=ORIGIN, end=WRONG_END),
            make_route_with_endpoints("bad2", duration_s=1100, start=ORIGIN, end=WRONG_END),
        ]
    )
    service = RouteAlternativesService(provider)

    with pytest.raises(ProviderError):
        service.get_routes(ORIGIN, DESTINATION, VEHICLE)
