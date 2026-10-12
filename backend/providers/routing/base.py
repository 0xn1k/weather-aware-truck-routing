from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.models import Coordinate, Route, Vehicle


@dataclass(frozen=True)
class RoutePreferences:
    """Truck-costing bias knobs used to generate the "preference variant"
    routes in the 3-route pipeline (backend/README.md Section 5.1, step 2).
    0.0-1.0, Valhalla's own costing-option range; a different provider is
    free to interpret or ignore fields it doesn't support."""

    use_highways: float | None = None
    use_tolls: float | None = None


class RoutingProvider(Protocol):
    def routes(
        self,
        origin: Coordinate,
        destination: Coordinate,
        *,
        vehicle: Vehicle,
        alternates: int = 0,
        preferences: RoutePreferences | None = None,
        via: Coordinate | None = None,
    ) -> list[Route]: ...
