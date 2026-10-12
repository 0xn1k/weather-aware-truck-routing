import pytest

from core.geo import bearing, haversine, interpolate, offset_point, overlap_ratio, simplify
from core.models import Coordinate

CHICAGO = Coordinate(lat=41.8781, lon=-87.6298)
DENVER = Coordinate(lat=39.7392, lon=-104.9903)


def test_haversine_known_distance_chicago_denver():
    # Straight-line distance is ~920 miles; driving distance (1012 mi in the
    # API contract example) is naturally longer than straight-line.
    dist = haversine(CHICAGO, DENVER)
    assert 900 <= dist <= 940


def test_haversine_same_point_is_zero():
    assert haversine(CHICAGO, CHICAGO) == pytest.approx(0.0, abs=1e-9)


def test_haversine_one_degree_longitude_at_equator():
    a = Coordinate(lat=0, lon=0)
    b = Coordinate(lat=0, lon=1)
    # 1 degree of longitude at the equator is ~69.09 mi using Earth's MEAN
    # radius (3958.76 mi, EARTH_RADIUS_MI in core/geo.py) — the right choice
    # for a haversine used at arbitrary latitudes. The commonly quoted 69.17
    # mi figure uses the slightly larger equatorial radius instead.
    assert haversine(a, b) == pytest.approx(69.09, abs=0.05)


def test_interpolate_midpoint():
    mid = interpolate(CHICAGO, DENVER, 0.5)
    assert mid.lat == pytest.approx((CHICAGO.lat + DENVER.lat) / 2)
    assert mid.lon == pytest.approx((CHICAGO.lon + DENVER.lon) / 2)


def test_interpolate_endpoints():
    assert interpolate(CHICAGO, DENVER, 0.0) == CHICAGO
    assert interpolate(CHICAGO, DENVER, 1.0) == DENVER


def test_bearing_due_east_is_90():
    a = Coordinate(lat=0, lon=0)
    b = Coordinate(lat=0, lon=1)
    assert bearing(a, b) == pytest.approx(90, abs=0.1)


def test_bearing_due_north_is_0():
    a = Coordinate(lat=0, lon=0)
    b = Coordinate(lat=1, lon=0)
    assert bearing(a, b) == pytest.approx(0, abs=0.1)


def test_bearing_due_south_is_180():
    a = Coordinate(lat=0, lon=0)
    b = Coordinate(lat=-1, lon=0)
    assert bearing(a, b) == pytest.approx(180, abs=0.1)


def test_bearing_due_west_is_270():
    a = Coordinate(lat=0, lon=0)
    b = Coordinate(lat=0, lon=-1)
    assert bearing(a, b) == pytest.approx(270, abs=0.1)


def test_bearing_and_offset_point_round_trip():
    brng = bearing(CHICAGO, DENVER)
    dist = haversine(CHICAGO, DENVER)
    moved = offset_point(CHICAGO, brng, dist)
    assert moved.lat == pytest.approx(DENVER.lat, abs=0.01)
    assert moved.lon == pytest.approx(DENVER.lon, abs=0.01)


def test_offset_point_distance_matches_haversine():
    moved = offset_point(CHICAGO, bearing_deg=90, distance_mi=50)
    assert haversine(CHICAGO, moved) == pytest.approx(50, abs=0.5)


def test_offset_point_due_north_increases_latitude():
    moved = offset_point(CHICAGO, bearing_deg=0, distance_mi=10)
    assert moved.lat > CHICAGO.lat
    assert moved.lon == pytest.approx(CHICAGO.lon, abs=0.01)


def test_overlap_ratio_identical_routes_is_full():
    route = [CHICAGO, interpolate(CHICAGO, DENVER, 0.5), DENVER]
    assert overlap_ratio(route, route, threshold_mi=1.0) == 1.0


def test_overlap_ratio_far_apart_routes_is_zero():
    route_a = [CHICAGO]
    route_b = [DENVER]
    assert overlap_ratio(route_a, route_b, threshold_mi=1.0) == 0.0


def test_overlap_ratio_empty_route_a_is_zero():
    assert overlap_ratio([], [CHICAGO], threshold_mi=1.0) == 0.0


def test_overlap_ratio_partial_overlap():
    close_to_chicago = Coordinate(lat=CHICAGO.lat + 0.001, lon=CHICAGO.lon)
    route_a = [CHICAGO, close_to_chicago, DENVER]
    route_b = [CHICAGO]
    # Only the two Chicago-area points are within 1 mile of route_b.
    assert overlap_ratio(route_a, route_b, threshold_mi=1.0) == pytest.approx(2 / 3)


def test_simplify_straight_line_collapses_to_endpoints():
    points = [Coordinate(lat=i * 0.01, lon=0) for i in range(20)]
    result = simplify(points, tolerance_mi=0.5)
    assert result == [points[0], points[-1]]


def test_simplify_keeps_a_sharp_bend():
    # An L-shaped path: the corner point is ~0.69 mi off the straight
    # start-end line, so a tight tolerance must keep it.
    points = [
        Coordinate(lat=0, lon=0),
        Coordinate(lat=0, lon=0.01),
        Coordinate(lat=0.01, lon=0.01),
    ]
    result = simplify(points, tolerance_mi=0.1)
    assert points[1] in result


def test_simplify_short_input_is_unchanged():
    points = [CHICAGO, DENVER]
    assert simplify(points, tolerance_mi=0.1) == points
