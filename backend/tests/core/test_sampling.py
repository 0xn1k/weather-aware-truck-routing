from datetime import UTC, datetime

import pytest

from core.geo import haversine, interpolate
from core.models import Coordinate, Maneuver
from core.sampling import cumulative_miles, cumulative_seconds, sample_checkpoints

ORIGIN = Coordinate(lat=0, lon=0)
DESTINATION = Coordinate(lat=0, lon=2)  # ~138.18 mi east along the equator
DEPARTURE = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC)


def straight_line(n_points: int) -> list[Coordinate]:
    return [interpolate(ORIGIN, DESTINATION, i / (n_points - 1)) for i in range(n_points)]


def test_cumulative_miles_starts_at_zero_and_ends_at_total_distance():
    points = straight_line(50)
    cum = cumulative_miles(points)
    assert cum[0] == 0.0
    assert cum[-1] == pytest.approx(haversine(ORIGIN, DESTINATION), rel=1e-6)


def test_cumulative_miles_is_non_decreasing():
    points = straight_line(50)
    cum = cumulative_miles(points)
    assert all(b >= a for a, b in zip(cum, cum[1:]))


def test_cumulative_miles_empty_input():
    assert cumulative_miles([]) == []


def test_cumulative_seconds_single_maneuver_spans_whole_route():
    points = straight_line(5)
    cum_miles = cumulative_miles(points)
    maneuvers = [Maneuver(time_s=7200, begin_shape_index=0, end_shape_index=4)]
    cum_sec = cumulative_seconds(points, cum_miles, maneuvers)
    assert cum_sec[0] == 0.0
    assert cum_sec[-1] == pytest.approx(7200, rel=1e-6)
    # Evenly spaced points on a straight line -> evenly spaced time too.
    assert cum_sec[2] == pytest.approx(3600, rel=1e-6)


def test_cumulative_seconds_multiple_maneuvers_hand_off_correctly():
    points = straight_line(5)  # 4 equal-length segments
    cum_miles = cumulative_miles(points)
    maneuvers = [
        Maneuver(time_s=100, begin_shape_index=0, end_shape_index=2),
        Maneuver(time_s=50, begin_shape_index=2, end_shape_index=4),
    ]
    cum_sec = cumulative_seconds(points, cum_miles, maneuvers)
    assert cum_sec[2] == pytest.approx(100, rel=1e-6)
    assert cum_sec[4] == pytest.approx(150, rel=1e-6)


def test_sample_checkpoints_mile_markers_and_count():
    points = straight_line(201)
    maneuvers = [Maneuver(time_s=7200, begin_shape_index=0, end_shape_index=200)]
    checkpoints = sample_checkpoints(points, maneuvers, interval_mi=25, departure_time=DEPARTURE)

    total_mi = cumulative_miles(points)[-1]
    expected_markers = [0, 25, 50, 75, 100, 125, total_mi]
    assert [cp.mile_marker for cp in checkpoints] == pytest.approx(expected_markers)


def test_sample_checkpoints_etas_always_increase():
    points = straight_line(201)
    maneuvers = [Maneuver(time_s=7200, begin_shape_index=0, end_shape_index=200)]
    checkpoints = sample_checkpoints(points, maneuvers, interval_mi=25, departure_time=DEPARTURE)

    etas = [cp.eta for cp in checkpoints]
    assert all(b > a for a, b in zip(etas, etas[1:]))
    assert etas[0] == DEPARTURE


def test_sample_checkpoints_final_eta_matches_total_drive_time():
    points = straight_line(201)
    maneuvers = [Maneuver(time_s=7200, begin_shape_index=0, end_shape_index=200)]
    checkpoints = sample_checkpoints(points, maneuvers, interval_mi=25, departure_time=DEPARTURE)

    seconds_elapsed = (checkpoints[-1].eta - DEPARTURE).total_seconds()
    assert seconds_elapsed == pytest.approx(7200, rel=1e-6)


def test_sample_checkpoints_segment_miles_sum_to_route_length():
    points = straight_line(201)
    maneuvers = [Maneuver(time_s=7200, begin_shape_index=0, end_shape_index=200)]
    checkpoints = sample_checkpoints(points, maneuvers, interval_mi=25, departure_time=DEPARTURE)

    total_mi = cumulative_miles(points)[-1]
    assert sum(cp.segment_miles for cp in checkpoints) == pytest.approx(total_mi, rel=1e-6)


def test_sample_checkpoints_interval_larger_than_route_still_includes_endpoints():
    points = straight_line(10)  # short route, ~138 mi total
    maneuvers = [Maneuver(time_s=3600, begin_shape_index=0, end_shape_index=9)]
    checkpoints = sample_checkpoints(points, maneuvers, interval_mi=500, departure_time=DEPARTURE)

    total_mi = cumulative_miles(points)[-1]
    assert [cp.mile_marker for cp in checkpoints] == pytest.approx([0, total_mi])
