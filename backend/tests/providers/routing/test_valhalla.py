import json

import httpx
import polyline as polyline_lib
import pytest
import respx

from core.models import Coordinate, Vehicle
from providers.errors import NoRouteError, ProviderError
from providers.routing.valhalla import ValhallaRoutingProvider

BASE_URL = "https://api.stadiamaps.com"
ORIGIN = Coordinate(lat=41.8781, lon=-87.6298)
DESTINATION = Coordinate(lat=39.7392, lon=-104.9903)
VEHICLE = Vehicle(load_lb=38_000, empty_weight_lb=35_000)

ROUTE_POINTS = [(41.8781, -87.6298), (40.0, -95.0), (39.7392, -104.9903)]
SHAPE = polyline_lib.encode(ROUTE_POINTS, precision=6)

TRIP = {
    "summary": {"time": 7200.5, "length": 921.3},
    "legs": [
        {
            "shape": SHAPE,
            "maneuvers": [
                {"time": 3600.0, "begin_shape_index": 0, "end_shape_index": 1},
                {"time": 3600.5, "begin_shape_index": 1, "end_shape_index": 2},
            ],
        }
    ],
}
TRIP_RESPONSE = {"trip": TRIP}


VIA = Coordinate(lat=38.0, lon=-90.0)

# A `via` point makes this a multi-location request — Valhalla returns one
# leg per consecutive location pair. Leg 1 deliberately repeats the via
# point as its own first point (Valhalla's real behaviour), to exercise
# the junction-point de-dup.
LEG0_POINTS = [(41.8781, -87.6298), (40.5, -90.0), (38.0, -90.0)]  # origin -> via
LEG1_POINTS = [(38.0, -90.0), (38.5, -95.0), (39.7392, -104.9903)]  # via -> destination
MULTI_LEG_TRIP = {
    "summary": {"time": 450.0, "length": 50.0},
    "legs": [
        {
            "shape": polyline_lib.encode(LEG0_POINTS, precision=6),
            "maneuvers": [
                {"time": 100.0, "begin_shape_index": 0, "end_shape_index": 1},
                {"time": 150.0, "begin_shape_index": 1, "end_shape_index": 2},
            ],
        },
        {
            "shape": polyline_lib.encode(LEG1_POINTS, precision=6),
            "maneuvers": [
                {"time": 200.0, "begin_shape_index": 0, "end_shape_index": 2},
            ],
        },
    ],
}


@respx.mock
def test_via_route_continues_through_every_leg_to_the_real_destination():
    # Regression test for a confirmed bug: only legs[0] was ever read, so
    # a via/detour route's geometry stopped at the via point instead of
    # reaching the actual destination (found by comparing served geometry
    # against the real destination coordinate on a live request).
    respx.post(f"{BASE_URL}/route").mock(
        return_value=httpx.Response(200, json={"trip": MULTI_LEG_TRIP})
    )
    provider = ValhallaRoutingProvider(base_url=BASE_URL)

    routes = provider.routes(ORIGIN, DESTINATION, vehicle=VEHICLE, via=VIA)

    route = routes[0]
    assert route.geometry[-1].lat == pytest.approx(DESTINATION.lat, abs=1e-4)
    assert route.geometry[-1].lon == pytest.approx(DESTINATION.lon, abs=1e-4)


@respx.mock
def test_via_route_dedupes_the_shared_junction_point_between_legs():
    respx.post(f"{BASE_URL}/route").mock(
        return_value=httpx.Response(200, json={"trip": MULTI_LEG_TRIP})
    )
    provider = ValhallaRoutingProvider(base_url=BASE_URL)

    route = provider.routes(ORIGIN, DESTINATION, vehicle=VEHICLE, via=VIA)[0]

    # 3 points in each leg, minus the 1 point they share at the via
    # junction = 5, not 6.
    assert len(route.geometry) == 5
    assert route.geometry[2].lat == pytest.approx(VIA.lat, abs=1e-4)
    assert route.geometry[2].lon == pytest.approx(VIA.lon, abs=1e-4)


@respx.mock
def test_via_route_maneuver_indices_are_offset_into_the_combined_geometry():
    respx.post(f"{BASE_URL}/route").mock(
        return_value=httpx.Response(200, json={"trip": MULTI_LEG_TRIP})
    )
    provider = ValhallaRoutingProvider(base_url=BASE_URL)

    route = provider.routes(ORIGIN, DESTINATION, vehicle=VEHICLE, via=VIA)[0]

    assert len(route.maneuvers) == 3
    # Leg 0's two maneuvers are unaffected (no points dropped before them).
    assert (route.maneuvers[0].begin_shape_index, route.maneuvers[0].end_shape_index) == (0, 1)
    assert (route.maneuvers[1].begin_shape_index, route.maneuvers[1].end_shape_index) == (1, 2)
    # Leg 1's maneuver was local (0, 2); shifted by leg 0's 3 points minus
    # the 1 deduped junction point = +2, landing on (2, 4) — index 2 is
    # the via point shared with leg 0's last point, index 4 is the route's
    # actual last point (the destination).
    assert (route.maneuvers[2].begin_shape_index, route.maneuvers[2].end_shape_index) == (2, 4)


@respx.mock
def test_parses_distance_duration_and_geometry():
    respx.post(f"{BASE_URL}/route").mock(return_value=httpx.Response(200, json=TRIP_RESPONSE))
    provider = ValhallaRoutingProvider(base_url=BASE_URL, api_key="test-key")

    routes = provider.routes(ORIGIN, DESTINATION, vehicle=VEHICLE)

    assert len(routes) == 1
    route = routes[0]
    assert route.distance_mi == 921.3
    assert route.duration_s == 7200  # rounded from 7200.5
    assert len(route.geometry) == 3
    assert route.geometry[0].lat == pytest.approx(41.8781, abs=1e-5)
    assert route.geometry[-1].lon == pytest.approx(-104.9903, abs=1e-5)


@respx.mock
def test_maneuvers_carry_through_with_correct_shape_indices():
    respx.post(f"{BASE_URL}/route").mock(return_value=httpx.Response(200, json=TRIP_RESPONSE))
    provider = ValhallaRoutingProvider(base_url=BASE_URL)

    routes = provider.routes(ORIGIN, DESTINATION, vehicle=VEHICLE)

    maneuvers = routes[0].maneuvers
    assert len(maneuvers) == 2
    assert maneuvers[0].time_s == 3600.0
    assert maneuvers[0].begin_shape_index == 0
    assert maneuvers[0].end_shape_index == 1
    assert maneuvers[1].end_shape_index == 2


@respx.mock
def test_alternates_parsed_as_additional_routes_with_distinct_ids():
    response = {"trip": TRIP, "alternates": [{"trip": TRIP}]}
    respx.post(f"{BASE_URL}/route").mock(return_value=httpx.Response(200, json=response))
    provider = ValhallaRoutingProvider(base_url=BASE_URL)

    routes = provider.routes(ORIGIN, DESTINATION, vehicle=VEHICLE, alternates=1)

    assert len(routes) == 2
    assert routes[0].id != routes[1].id


@respx.mock
def test_truck_weight_sent_in_metric_tons():
    route_mock = respx.post(f"{BASE_URL}/route").mock(
        return_value=httpx.Response(200, json=TRIP_RESPONSE)
    )
    provider = ValhallaRoutingProvider(base_url=BASE_URL)

    provider.routes(ORIGIN, DESTINATION, vehicle=Vehicle(load_lb=38_000, empty_weight_lb=35_000))

    body = json.loads(route_mock.calls.last.request.content)
    # (38,000 + 35,000) lb * 0.000453592 = 33.11... metric tons
    assert body["costing_options"]["truck"]["weight"] == pytest.approx(33.11, abs=0.01)


@respx.mock
def test_no_date_time_is_ever_sent():
    route_mock = respx.post(f"{BASE_URL}/route").mock(
        return_value=httpx.Response(200, json=TRIP_RESPONSE)
    )
    provider = ValhallaRoutingProvider(base_url=BASE_URL)

    provider.routes(ORIGIN, DESTINATION, vehicle=VEHICLE, alternates=2)

    body = json.loads(route_mock.calls.last.request.content)
    assert "date_time" not in body


@respx.mock
def test_does_not_send_alternates_when_via_is_set():
    route_mock = respx.post(f"{BASE_URL}/route").mock(
        return_value=httpx.Response(200, json=TRIP_RESPONSE)
    )
    provider = ValhallaRoutingProvider(base_url=BASE_URL)

    provider.routes(
        ORIGIN,
        DESTINATION,
        vehicle=VEHICLE,
        alternates=2,
        via=Coordinate(lat=40.5, lon=-95.0),
    )

    body = json.loads(route_mock.calls.last.request.content)
    assert "alternates" not in body
    assert len(body["locations"]) == 3


@respx.mock
def test_no_route_raises_no_route_error():
    respx.post(f"{BASE_URL}/route").mock(
        return_value=httpx.Response(400, json={"error": "No path could be found for input"})
    )
    provider = ValhallaRoutingProvider(base_url=BASE_URL)

    with pytest.raises(NoRouteError):
        provider.routes(ORIGIN, DESTINATION, vehicle=VEHICLE)


@respx.mock
def test_distance_cap_error_gets_a_plain_english_message():
    # Regression test: Valhalla's raw {"error_code":154,...} JSON body was
    # leaking straight into the API error response and the UI, verbatim.
    respx.post(f"{BASE_URL}/route").mock(
        return_value=httpx.Response(
            400,
            json={
                "error_code": 154,
                "error": "Path distance exceeds the max distance limit: 1500000 meters",
                "status_code": 400,
                "status": "Bad Request",
            },
        )
    )
    provider = ValhallaRoutingProvider(base_url=BASE_URL)

    with pytest.raises(NoRouteError) as exc_info:
        provider.routes(ORIGIN, DESTINATION, vehicle=VEHICLE)

    message = str(exc_info.value)
    assert "error_code" not in message
    assert "too long" in message


@respx.mock
def test_server_error_raises_provider_error_after_retries():
    route_mock = respx.post(f"{BASE_URL}/route").mock(return_value=httpx.Response(500))
    provider = ValhallaRoutingProvider(base_url=BASE_URL, retries=2, timeout_s=1.0)

    with pytest.raises(ProviderError):
        provider.routes(ORIGIN, DESTINATION, vehicle=VEHICLE)

    assert route_mock.call_count == 3  # 1 initial attempt + 2 retries


@respx.mock
def test_recovers_if_a_retry_succeeds():
    route_mock = respx.post(f"{BASE_URL}/route").mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json=TRIP_RESPONSE)]
    )
    provider = ValhallaRoutingProvider(base_url=BASE_URL, retries=2, timeout_s=1.0)

    routes = provider.routes(ORIGIN, DESTINATION, vehicle=VEHICLE)

    assert len(routes) == 1
    assert route_mock.call_count == 2
