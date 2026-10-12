from datetime import UTC, datetime

import pytest

from core.models import (
    Checkpoint,
    Coordinate,
    PeakReading,
    RiskLevel,
    RiskResult,
    Route,
    RouteSummary,
    WeatherSample,
)
from core.ranking import rank, summarize

ETA = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC)


def cp(
    mile: float,
    segment_miles: float,
    level: RiskLevel,
    wind: float = 10.0,
    rain: float = 0.0,
    snow: float = 0.0,
    driver: str = "wind",
) -> Checkpoint:
    return Checkpoint(
        position=Coordinate(lat=0, lon=mile * 0.01),
        mile_marker=mile,
        segment_miles=segment_miles,
        eta=ETA,
        weather=WeatherSample(wind_mph=wind, gust_mph=wind + 5, rain_in_hr=rain, snow_in_hr=snow),
        risk=RiskResult(level=level, driver=driver),
    )


def route(route_id: str = "r1", duration_s: int = 3600) -> Route:
    return Route(
        id=route_id,
        label="Test route",
        geometry=[Coordinate(lat=0, lon=0), Coordinate(lat=0, lon=1)],
        distance_mi=100,
        duration_s=duration_s,
    )


# ---- summarize() ----


def test_miles_by_level_sums_correctly_and_covers_all_levels():
    checkpoints = [
        cp(0, 10, RiskLevel.LOW),
        cp(10, 20, RiskLevel.MODERATE),
        cp(30, 15, RiskLevel.LOW),
    ]
    summary = summarize(route(), checkpoints)
    assert summary.miles_by_level[RiskLevel.LOW] == 25
    assert summary.miles_by_level[RiskLevel.MODERATE] == 20
    assert summary.miles_by_level[RiskLevel.HIGH] == 0
    assert summary.miles_by_level[RiskLevel.SEVERE] == 0
    assert summary.miles_by_level[RiskLevel.NO_TRAVEL] == 0
    assert sum(summary.miles_by_level.values()) == pytest.approx(45)


def test_avg_risk_is_miles_weighted_not_a_simple_average():
    # A long Low stretch and a short Severe stretch: a simple average of
    # levels (0 + 3) / 2 = 1.5 would be wrong. Weighted by miles it should
    # sit close to Low.
    checkpoints = [
        cp(0, 90, RiskLevel.LOW),
        cp(90, 10, RiskLevel.SEVERE),
    ]
    summary = summarize(route(), checkpoints)
    # (0*90 + 3*10) / 100 = 0.3
    assert summary.avg_risk == pytest.approx(0.3)


def test_max_level_is_the_single_worst_level_reached():
    checkpoints = [
        cp(0, 10, RiskLevel.LOW),
        cp(10, 10, RiskLevel.HIGH),
        cp(20, 10, RiskLevel.MODERATE),
    ]
    summary = summarize(route(), checkpoints)
    assert summary.max_level == RiskLevel.HIGH


def test_worst_checkpoint_ties_go_to_the_earliest_mile():
    checkpoints = [
        cp(50, 10, RiskLevel.SEVERE),
        cp(10, 10, RiskLevel.SEVERE),  # earlier, same level -> wins the tie
        cp(30, 10, RiskLevel.LOW),
    ]
    summary = summarize(route(), checkpoints)
    assert summary.worst_checkpoint.mile_marker == 10


def test_peaks_are_independent_of_which_checkpoint_is_worst_overall():
    # The highest wind reading is at a Low-risk checkpoint; the worst
    # overall checkpoint is driven by snow instead. Peaks must still report
    # the true highest wind, not the wind value at the worst stop.
    checkpoints = [
        cp(0, 10, RiskLevel.LOW, wind=40.0, rain=0, snow=0),
        cp(10, 10, RiskLevel.SEVERE, wind=5.0, rain=0, snow=2.5, driver="snow"),
    ]
    summary = summarize(route(), checkpoints)
    assert summary.peak_wind.value == 40.0
    assert summary.peak_wind.checkpoint.mile_marker == 0
    assert summary.peak_snow.value == 2.5
    assert summary.peak_snow.checkpoint.mile_marker == 10


def test_duration_s_carries_through_from_the_route():
    checkpoints = [cp(0, 50, RiskLevel.LOW), cp(50, 50, RiskLevel.LOW)]
    summary = summarize(route(duration_s=5400), checkpoints)
    assert summary.duration_s == 5400


# ---- rank() ----


def summary(
    no_travel: float = 0,
    severe: float = 0,
    high: float = 0,
    avg_risk: float = 0.0,
    duration_s: int = 3600,
) -> RouteSummary:
    worst = cp(0, 1, RiskLevel.LOW)
    peak = cp(0, 1, RiskLevel.LOW)
    return RouteSummary(
        miles_by_level={
            RiskLevel.LOW: 0,
            RiskLevel.MODERATE: 0,
            RiskLevel.HIGH: high,
            RiskLevel.SEVERE: severe,
            RiskLevel.NO_TRAVEL: no_travel,
        },
        avg_risk=avg_risk,
        max_level=RiskLevel.LOW,
        worst_checkpoint=worst,
        peak_wind=PeakReading(checkpoint=peak, value=0.0),
        peak_rain=PeakReading(checkpoint=peak, value=0.0),
        peak_snow=PeakReading(checkpoint=peak, value=0.0),
        duration_s=duration_s,
    )


def test_rank_no_travel_miles_decides_first():
    summaries = {
        "a": summary(no_travel=5, duration_s=1000),
        "b": summary(no_travel=0, duration_s=9000),
    }
    assert rank(summaries) == ["b", "a"]


def test_rank_falls_through_to_severe_when_no_travel_tied():
    summaries = {
        "a": summary(severe=10),
        "b": summary(severe=2),
    }
    assert rank(summaries) == ["b", "a"]


def test_rank_falls_through_to_high_when_severe_tied():
    summaries = {
        "a": summary(high=20),
        "b": summary(high=5),
    }
    assert rank(summaries) == ["b", "a"]


def test_rank_falls_through_to_avg_risk_when_high_tied():
    summaries = {
        "a": summary(avg_risk=0.9),
        "b": summary(avg_risk=0.2),
    }
    assert rank(summaries) == ["b", "a"]


def test_rank_falls_through_to_duration_when_everything_else_tied():
    summaries = {
        "a": summary(duration_s=20_000),
        "b": summary(duration_s=10_000),
    }
    assert rank(summaries) == ["b", "a"]


def test_rank_no_travel_route_always_loses_to_a_clean_one_even_if_much_faster():
    summaries = {
        "fast_but_no_travel": summary(no_travel=1, duration_s=100),
        "slow_but_clean": summary(no_travel=0, duration_s=50_000),
    }
    assert rank(summaries) == ["slow_but_clean", "fast_but_no_travel"]
