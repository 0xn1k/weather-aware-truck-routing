import pytest

from core.models import RiskLevel, WeatherSample
from core.risk.classifier import classify

LOW_LOAD = 10_000  # never triggers a load rule


def sample(wind=0.0, rain=0.0, snow=0.0, gust=0.0):
    return WeatherSample(wind_mph=wind, gust_mph=gust, rain_in_hr=rain, snow_in_hr=snow)


@pytest.mark.parametrize(
    "wind,expected",
    [
        (0, RiskLevel.LOW),
        (24.9, RiskLevel.LOW),
        (25, RiskLevel.MODERATE),
        (34.9, RiskLevel.MODERATE),
        (35, RiskLevel.HIGH),
        (44.9, RiskLevel.HIGH),
        (45, RiskLevel.SEVERE),
        (54.9, RiskLevel.SEVERE),
        (55, RiskLevel.NO_TRAVEL),
        (70, RiskLevel.NO_TRAVEL),
    ],
)
def test_wind_thresholds(wind, expected):
    result = classify(sample(wind=wind), LOW_LOAD)
    assert result.level == expected
    assert result.driver == "wind"


@pytest.mark.parametrize(
    "rain,expected",
    [
        (0.00, RiskLevel.LOW),
        (0.09, RiskLevel.LOW),
        (0.10, RiskLevel.MODERATE),
        (0.24, RiskLevel.MODERATE),
        (0.25, RiskLevel.HIGH),
        (0.49, RiskLevel.HIGH),
        (0.50, RiskLevel.SEVERE),
        (1.00, RiskLevel.SEVERE),
        (1.01, RiskLevel.NO_TRAVEL),
    ],
)
def test_rain_thresholds(rain, expected):
    result = classify(sample(rain=rain), LOW_LOAD)
    assert result.level == expected
    if expected != RiskLevel.LOW:  # at Low, wind/rain/snow all tie at 0 — driver is arbitrary
        assert result.driver == "rain"


@pytest.mark.parametrize(
    "snow,expected",
    [
        (0.0, RiskLevel.LOW),
        (0.4, RiskLevel.LOW),
        (0.5, RiskLevel.MODERATE),
        (0.9, RiskLevel.MODERATE),
        (1.0, RiskLevel.HIGH),
        (1.9, RiskLevel.HIGH),
        (2.0, RiskLevel.SEVERE),
        (3.0, RiskLevel.SEVERE),
        (3.01, RiskLevel.NO_TRAVEL),
    ],
)
def test_snow_thresholds(snow, expected):
    result = classify(sample(snow=snow), LOW_LOAD)
    assert result.level == expected
    if expected != RiskLevel.LOW:  # at Low, wind/rain/snow all tie at 0 — driver is arbitrary
        assert result.driver == "snow"


def test_tie_break_order_is_wind_then_rain_then_snow():
    # All three factors are tied at Low — classify() must still return a
    # deterministic driver. This pins that order down explicitly so a future
    # change to by_factor's construction (e.g. the registry pattern discussed
    # for additional hazards) can't silently change it without failing a test.
    result = classify(sample(wind=0, rain=0, snow=0), LOW_LOAD)
    assert result.level == RiskLevel.LOW
    assert result.driver == "wind"


def test_worst_factor_drives_the_result():
    # rain -> High (0.25), snow -> Moderate (0.5): rain is worse, so it drives.
    result = classify(sample(rain=0.25, snow=0.5), LOW_LOAD)
    assert result.level == RiskLevel.HIGH
    assert result.driver == "rain"


@pytest.mark.parametrize(
    "wind,load,expected_level,expected_driver",
    [
        (40, 40_000, RiskLevel.HIGH, "wind"),  # exactly 40,000 is not "over" -> rule doesn't apply
        (40, 40_001, RiskLevel.SEVERE, "load_rule"),  # 35-44 mph + load > 40,000 -> Severe
        (50, 30_000, RiskLevel.SEVERE, "wind"),  # exactly 30,000 is not "over" -> no rule applies
        (50, 30_001, RiskLevel.NO_TRAVEL, "load_rule"),  # 45-54 mph + load > 30,000 -> No Travel
        (60, 1, RiskLevel.NO_TRAVEL, "wind"),  # wind alone is already No Travel; rule is a no-op
    ],
)
def test_load_rules(wind, load, expected_level, expected_driver):
    result = classify(sample(wind=wind), load)
    assert result.level == expected_level
    assert result.driver == expected_driver
