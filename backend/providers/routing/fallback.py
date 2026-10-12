from __future__ import annotations

from core.models import Coordinate, Route, Vehicle
from providers.errors import ProviderError
from providers.routing.base import RoutePreferences, RoutingProvider


class FallbackRoutingProvider:
    """Tries `primary`; if it raises ProviderError (outage, timeout),
    retries the whole request against `secondary` (Stadia, then the public
    Valhalla server). A NoRouteError is a real answer, not a failure, so it
    is NOT retried against the secondary — a different server backed by the
    same road network won't find a path the first one couldn't."""

    def __init__(self, primary: RoutingProvider, secondary: RoutingProvider):
        self.primary = primary
        self.secondary = secondary

    def routes(
        self,
        origin: Coordinate,
        destination: Coordinate,
        *,
        vehicle: Vehicle,
        alternates: int = 0,
        preferences: RoutePreferences | None = None,
        via: Coordinate | None = None,
    ) -> list[Route]:
        try:
            return self.primary.routes(
                origin,
                destination,
                vehicle=vehicle,
                alternates=alternates,
                preferences=preferences,
                via=via,
            )
        except ProviderError:
            return self.secondary.routes(
                origin,
                destination,
                vehicle=vehicle,
                alternates=alternates,
                preferences=preferences,
                via=via,
            )
