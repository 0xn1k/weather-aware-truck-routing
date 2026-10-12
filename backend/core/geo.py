from __future__ import annotations

import math

from core.models import Coordinate

EARTH_RADIUS_MI = 3958.7613


def haversine(a: Coordinate, b: Coordinate) -> float:
    """Great-circle distance between two points, in miles."""
    lat1, lon1 = math.radians(a.lat), math.radians(a.lon)
    lat2, lon2 = math.radians(b.lat), math.radians(b.lon)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


def point_within(a: Coordinate, b: Coordinate, tolerance_mi: float) -> bool:
    """Whether a and b are close enough to count as "the same point" — a
    routing engine snaps a requested lat/lon to the nearest routable road,
    so exact equality isn't realistic. Used to verify a route's geometry
    actually starts/ends at the requested origin/destination."""
    return haversine(a, b) <= tolerance_mi


def interpolate(a: Coordinate, b: Coordinate, fraction: float) -> Coordinate:
    """Point a fraction of the way from a to b. Linear in lat/lon, which is
    an accurate enough approximation for the short hops between adjacent
    points in a decoded route geometry (see sampling.py)."""
    return Coordinate(
        lat=a.lat + (b.lat - a.lat) * fraction,
        lon=a.lon + (b.lon - a.lon) * fraction,
    )


def bearing(a: Coordinate, b: Coordinate) -> float:
    """Initial great-circle bearing from a to b, in degrees [0, 360),
    0 = north, 90 = east. Used by the detour step of the 3-route pipeline
    to find the direction perpendicular to a route at a given point."""
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlon = math.radians(b.lon - a.lon)
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return math.degrees(math.atan2(x, y)) % 360


def offset_point(origin: Coordinate, bearing_deg: float, distance_mi: float) -> Coordinate:
    """The point `distance_mi` from `origin` along initial bearing
    `bearing_deg` (0 = north, 90 = east), via the great-circle destination
    formula. Used by the detour step of the 3-route pipeline."""
    lat1 = math.radians(origin.lat)
    lon1 = math.radians(origin.lon)
    brng = math.radians(bearing_deg)
    d_r = distance_mi / EARTH_RADIUS_MI

    lat2 = math.asin(
        math.sin(lat1) * math.cos(d_r) + math.cos(lat1) * math.sin(d_r) * math.cos(brng)
    )
    lon2 = lon1 + math.atan2(
        math.sin(brng) * math.sin(d_r) * math.cos(lat1),
        math.cos(d_r) - math.sin(lat1) * math.sin(lat2),
    )
    return Coordinate(lat=math.degrees(lat2), lon=math.degrees(lon2))


def overlap_ratio(
    route_a: list[Coordinate], route_b: list[Coordinate], threshold_mi: float
) -> float:
    """Fraction of route_a's points that lie within threshold_mi of ANY
    point on route_b. Used to reject a route-alternative candidate that's
    really just the same route with minor wiggles (backend/README.md 5.1)."""
    if not route_a:
        return 0.0
    close = 0
    for p in route_a:
        if any(haversine(p, q) <= threshold_mi for q in route_b):
            close += 1
    return close / len(route_a)


def _to_local_mi(origin: Coordinate, point: Coordinate) -> tuple[float, float]:
    """Flat-earth projection onto a plane tangent at `origin`, in miles.
    Good enough for Douglas-Peucker's perpendicular-distance test over a
    single route's span — not meant for distances this function isn't used
    for (use haversine for those)."""
    lat_rad = math.radians(origin.lat)
    dx = (point.lon - origin.lon) * 69.172 * math.cos(lat_rad)
    dy = (point.lat - origin.lat) * 69.0
    return dx, dy


def _point_to_segment_distance_mi(point: Coordinate, start: Coordinate, end: Coordinate) -> float:
    px, py = _to_local_mi(start, point)
    ex, ey = _to_local_mi(start, end)
    seg_len_sq = ex * ex + ey * ey
    if seg_len_sq == 0:
        return math.hypot(px, py)
    t = max(0.0, min(1.0, (px * ex + py * ey) / seg_len_sq))
    cx, cy = ex * t, ey * t
    return math.hypot(px - cx, py - cy)


def simplify(points: list[Coordinate], tolerance_mi: float) -> list[Coordinate]:
    """Douglas-Peucker line simplification. Keeps the route's shape within
    tolerance_mi while cutting a dense geometry down to the ~500 points the
    frontend expects (frontend/README.md Section 7, "Map performance
    rules")."""
    if len(points) < 3:
        return list(points)

    start, end = points[0], points[-1]
    max_dist = -1.0
    split_at = 0
    for i in range(1, len(points) - 1):
        dist = _point_to_segment_distance_mi(points[i], start, end)
        if dist > max_dist:
            max_dist = dist
            split_at = i

    if max_dist > tolerance_mi:
        left = simplify(points[: split_at + 1], tolerance_mi)
        right = simplify(points[split_at:], tolerance_mi)
        return left[:-1] + right
    return [start, end]
