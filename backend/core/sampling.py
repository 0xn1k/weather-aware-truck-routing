from __future__ import annotations

from datetime import datetime, timedelta

from core.geo import haversine, interpolate
from core.models import CheckpointPlan, Coordinate, Maneuver


def cumulative_miles(points: list[Coordinate]) -> list[float]:
    """Cumulative distance from the start, at every geometry point."""
    if not points:
        return []
    miles = [0.0]
    for prev, cur in zip(points, points[1:]):
        miles.append(miles[-1] + haversine(prev, cur))
    return miles


def cumulative_seconds(
    points: list[Coordinate], cum_miles: list[float], maneuvers: list[Maneuver]
) -> list[float]:
    """Cumulative drive time from the start, at every geometry point.
    Each maneuver's time_s is spread over its points in proportion to the
    distance each one covers, since Valhalla gives timing per maneuver, not
    per point (backend/README.md Section 5.2, step 2)."""
    seconds = [0.0] * len(points)
    for m in maneuvers:
        begin, end = m.begin_shape_index, m.end_shape_index
        if begin >= end or end >= len(points):
            continue
        span_mi = cum_miles[end] - cum_miles[begin]
        n_points = end - begin
        for i in range(begin + 1, end + 1):
            if span_mi > 0:
                fraction = (cum_miles[i] - cum_miles[i - 1]) / span_mi
            else:
                fraction = 1 / n_points  # degenerate zero-length maneuver: split evenly
            seconds[i] = seconds[i - 1] + m.time_s * fraction
    return seconds


def _position_and_seconds_at_mile(
    points: list[Coordinate],
    cum_miles: list[float],
    cum_seconds: list[float],
    target_mile: float,
) -> tuple[Coordinate, float]:
    for i in range(len(cum_miles) - 1):
        if cum_miles[i] <= target_mile <= cum_miles[i + 1]:
            span = cum_miles[i + 1] - cum_miles[i]
            fraction = (target_mile - cum_miles[i]) / span if span > 0 else 0.0
            position = interpolate(points[i], points[i + 1], fraction)
            seconds = cum_seconds[i] + (cum_seconds[i + 1] - cum_seconds[i]) * fraction
            return position, seconds
    return points[-1], cum_seconds[-1]


def _target_miles(total_mi: float, interval_mi: float) -> list[float]:
    targets = [0.0]
    m = interval_mi
    while m < total_mi:
        targets.append(m)
        m += interval_mi
    if not targets or targets[-1] != total_mi:
        targets.append(total_mi)
    return targets


def sample_checkpoints(
    points: list[Coordinate],
    maneuvers: list[Maneuver],
    interval_mi: float,
    departure_time: datetime,
) -> list[CheckpointPlan]:
    """Mile 0, every interval_mi miles, and the destination — each with its
    interpolated position and ETA (departure_time + cumulative seconds)."""
    cum_miles = cumulative_miles(points)
    cum_seconds = cumulative_seconds(points, cum_miles, maneuvers)
    total_mi = cum_miles[-1] if cum_miles else 0.0

    targets = _target_miles(total_mi, interval_mi)
    positions_and_seconds = [
        _position_and_seconds_at_mile(points, cum_miles, cum_seconds, t) for t in targets
    ]

    checkpoints = []
    for i, (mile, (position, seconds)) in enumerate(zip(targets, positions_and_seconds)):
        prev_mile = targets[i - 1] if i > 0 else mile
        next_mile = targets[i + 1] if i < len(targets) - 1 else mile
        segment_miles = (next_mile - prev_mile) / 2
        checkpoints.append(
            CheckpointPlan(
                position=position,
                mile_marker=mile,
                segment_miles=segment_miles,
                eta=departure_time + timedelta(seconds=seconds),
            )
        )
    return checkpoints
