import pytest

from core.models import Coordinate, Route, Vehicle
from providers.errors import NoRouteError, ProviderError
from providers.routing.fallback import FallbackRoutingProvider

ORIGIN = Coordinate(lat=0, lon=0)
DESTINATION = Coordinate(lat=1, lon=1)
VEHICLE = Vehicle(load_lb=1_000, empty_weight_lb=35_000)


class FakeProvider:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.called = False

    def routes(self, origin, destination, *, vehicle, alternates=0, preferences=None, via=None):
        self.called = True
        if self.error:
            raise self.error
        return self.result


def make_route(route_id: str) -> Route:
    return Route(
        id=route_id, label="", geometry=[ORIGIN, DESTINATION], distance_mi=10, duration_s=600
    )


def test_uses_primary_when_it_succeeds():
    primary = FakeProvider(result=[make_route("primary")])
    secondary = FakeProvider(result=[make_route("secondary")])
    provider = FallbackRoutingProvider(primary, secondary)

    routes = provider.routes(ORIGIN, DESTINATION, vehicle=VEHICLE)

    assert routes[0].id == "primary"
    assert not secondary.called


def test_falls_back_to_secondary_on_provider_error():
    primary = FakeProvider(error=ProviderError("timeout"))
    secondary = FakeProvider(result=[make_route("secondary")])
    provider = FallbackRoutingProvider(primary, secondary)

    routes = provider.routes(ORIGIN, DESTINATION, vehicle=VEHICLE)

    assert routes[0].id == "secondary"
    assert secondary.called


def test_no_route_error_does_not_trigger_fallback():
    primary = FakeProvider(error=NoRouteError("no path"))
    secondary = FakeProvider(result=[make_route("secondary")])
    provider = FallbackRoutingProvider(primary, secondary)

    with pytest.raises(NoRouteError):
        provider.routes(ORIGIN, DESTINATION, vehicle=VEHICLE)

    assert not secondary.called


def test_secondary_failure_propagates_too():
    primary = FakeProvider(error=ProviderError("primary down"))
    secondary = FakeProvider(error=ProviderError("secondary down too"))
    provider = FallbackRoutingProvider(primary, secondary)

    with pytest.raises(ProviderError):
        provider.routes(ORIGIN, DESTINATION, vehicle=VEHICLE)
