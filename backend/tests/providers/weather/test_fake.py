from datetime import UTC, datetime

from core.models import Coordinate, RiskLevel
from core.risk.classifier import classify
from providers.weather.fake import FakeWeatherProvider

START = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC)
CHICAGO = Coordinate(lat=41.8781, lon=-87.6298)
DENVER = Coordinate(lat=39.7392, lon=-104.9903)


def test_returns_one_series_per_point_of_the_requested_length():
    provider = FakeWeatherProvider()

    result = provider.hourly([CHICAGO, DENVER], START, hours=49)

    assert set(result.keys()) == {CHICAGO, DENVER}
    assert len(result[CHICAGO]) == 49
    assert len(result[DENVER]) == 49


def test_same_point_and_hour_always_returns_the_same_sample():
    # Deterministic — a repeated request (e.g. re-running the same demo)
    # must produce the same weather, not a new random draw.
    provider = FakeWeatherProvider()

    first = provider.hourly([CHICAGO], START, hours=10)
    second = provider.hourly([CHICAGO], START, hours=10)

    assert first[CHICAGO] == second[CHICAGO]


def test_produces_a_mix_of_levels_below_no_travel_away_from_the_storm_cell():
    # Chicago is well outside the storm cell (see _STORM_CENTER) — this is
    # what an arbitrary point on an arbitrary trip actually samples, and it
    # must stay drivable (no No Travel), or almost every trip ends up
    # blocked by the "Do not travel" banner regardless of departure time or
    # load, as happened with an earlier version of this provider.
    provider = FakeWeatherProvider()

    series = provider.hourly([CHICAGO], START, hours=49)[CHICAGO]
    levels = {classify(sample, load_lb=38_000).level for sample in series}

    assert RiskLevel.NO_TRAVEL not in levels
    assert len(levels) > 1  # still a believable mix, not flat "Low" the whole time


def test_no_travel_is_reliably_reachable_inside_the_storm_cell():
    # The flip side of the above: No Travel must still be reachable on
    # demand for testing — just only via the deliberately-placed storm
    # cell, not scattered across arbitrary points.
    provider = FakeWeatherProvider()
    storm_point = Coordinate(lat=45.8, lon=-108.5)  # matches _STORM_CENTER

    series = provider.hourly([storm_point], START, hours=49)[storm_point]
    levels = {classify(sample, load_lb=38_000).level for sample in series}

    assert RiskLevel.NO_TRAVEL in levels


def test_different_points_peak_at_different_hours():
    # So a "storm" visibly moves across the map as the forecast slider
    # advances, instead of every point spiking in lockstep.
    provider = FakeWeatherProvider()

    result = provider.hourly([CHICAGO, DENVER], START, hours=49)
    chicago_winds = [s.wind_mph for s in result[CHICAGO]]
    denver_winds = [s.wind_mph for s in result[DENVER]]

    assert chicago_winds != denver_winds
