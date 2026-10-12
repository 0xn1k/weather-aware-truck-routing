from __future__ import annotations

from typing import Any

import httpx
import polyline

from core.models import Coordinate, Maneuver, Route, Vehicle
from providers.errors import NoRouteError, ProviderError
from providers.http import DEFAULT_HEADERS
from providers.routing.base import RoutePreferences

LB_TO_METRIC_TONS = 0.000453592
POLYLINE_PRECISION = 6
VALHALLA_MAX_DISTANCE_ERROR_CODE = 154


def _no_route_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return "No route found between origin and destination"
    if body.get("error_code") == VALHALLA_MAX_DISTANCE_ERROR_CODE:
        return (
            "This trip is too long for the routing service to plan "
            "(it only supports routes up to about 930 miles point-to-point). "
            "Try a shorter route or an intermediate stop."
        )
    return "No route found between origin and destination"


class ValhallaRoutingProvider:
    """Serves both Stadia-hosted Valhalla and the public Valhalla demo
    server — same API, only base_url and api_key differ
    (backend/README.md Section 4)."""

    def __init__(
        self, base_url: str, api_key: str = "", timeout_s: float = 10.0, retries: int = 2
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.retries = retries

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
        body = self._build_request(origin, destination, vehicle, alternates, preferences, via)
        data = self._post(body)
        return self._parse_response(data)

    def _build_request(
        self,
        origin: Coordinate,
        destination: Coordinate,
        vehicle: Vehicle,
        alternates: int,
        preferences: RoutePreferences | None,
        via: Coordinate | None,
    ) -> dict[str, Any]:
        locations = [self._location(origin)]
        if via is not None:
            locations.append(self._location(via))
        locations.append(self._location(destination))

        truck_options: dict[str, float] = {
            "weight": round(vehicle.total_weight_lb * LB_TO_METRIC_TONS, 2),
        }
        if preferences is not None:
            if preferences.use_highways is not None:
                truck_options["use_highways"] = preferences.use_highways
            if preferences.use_tolls is not None:
                truck_options["use_tolls"] = preferences.use_tolls

        body: dict[str, Any] = {
            "locations": locations,
            "costing": "truck",
            "costing_options": {"truck": truck_options},
            "units": "miles",
        }
        # Valhalla doesn't support alternates on time-dependent routes or
        # routes with more than 2 locations — we never send date_time, and a
        # `via` point means 3 locations, so alternates is skipped then too
        # (backend/README.md Section 5.1, step 1).
        if alternates and via is None:
            body["alternates"] = alternates
        return body

    @staticmethod
    def _location(point: Coordinate) -> dict[str, float]:
        return {"lat": point.lat, "lon": point.lon}

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/route"
        params = {"api_key": self.api_key} if self.api_key else {}
        last_error: Exception | None = None
        for _attempt in range(self.retries + 1):
            try:
                response = httpx.post(
                    url, json=body, params=params, headers=DEFAULT_HEADERS, timeout=self.timeout_s
                )
                if response.status_code == 400:
                    # Valhalla returns 400 for "no path could be found" — our
                    # own request construction is otherwise well-formed, so a
                    # 400 here means no route exists, not a malformed request.
                    # error_code 154 specifically means the two points are
                    # farther apart than Valhalla's own routing cap (1500 km)
                    # — a real, expected limit of the hosted service, not a
                    # bug, so it gets a plain-English message instead of the
                    # raw {"error_code":154,...} JSON surfacing to the user.
                    raise NoRouteError(_no_route_message(response))
                response.raise_for_status()
                result: dict[str, Any] = response.json()
                return result
            except NoRouteError:
                raise
            except httpx.HTTPError as exc:
                last_error = exc
        raise ProviderError(
            f"Valhalla request failed after {self.retries + 1} attempts: {last_error}"
        )

    def _parse_response(self, data: dict[str, Any]) -> list[Route]:
        trips = [data["trip"]] if "trip" in data else []
        trips += [alt["trip"] for alt in data.get("alternates", [])]
        return [self._parse_trip(i, trip) for i, trip in enumerate(trips)]

    def _parse_trip(self, index: int, trip: dict[str, Any]) -> Route:
        # A `via` point (the detour step) makes this a multi-location
        # request, and Valhalla returns one leg per consecutive location
        # pair — origin->via as legs[0], via->destination as legs[1].
        # Reading only legs[0] (an earlier bug, confirmed by comparing
        # served geometry against the real destination) silently dropped
        # every leg after the first, so a detour route's geometry stopped
        # at the via point instead of continuing to the destination.
        geometry: list[Coordinate] = []
        maneuvers: list[Maneuver] = []

        for leg in trip["legs"]:
            leg_points = [
                Coordinate(lat=lat, lon=lon)
                for lat, lon in polyline.decode(leg["shape"], precision=POLYLINE_PRECISION)
            ]
            # Consecutive legs share their junction point (the via
            # location) — each leg's own shape repeats it as both its own
            # last point and the next leg's first point. Drop that
            # duplicate, and shift this leg's maneuver shape-indices
            # (which are local to its own un-deduped shape) to match.
            offset = len(geometry)
            if geometry and leg_points:
                leg_points = leg_points[1:]
                offset -= 1

            for m in leg["maneuvers"]:
                maneuvers.append(
                    Maneuver(
                        time_s=m["time"],
                        begin_shape_index=m["begin_shape_index"] + offset,
                        end_shape_index=m["end_shape_index"] + offset,
                    )
                )
            geometry.extend(leg_points)

        return Route(
            id=f"r{index}",
            label="",  # assigned by RouteAlternativesService once candidates are filtered
            geometry=geometry,
            distance_mi=trip["summary"]["length"],
            duration_s=round(trip["summary"]["time"]),
            maneuvers=maneuvers,
        )
