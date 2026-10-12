from __future__ import annotations

from core.models import RiskLevel, RiskResult, WeatherSample
from core.risk.rules import LOAD_RULES, RAIN_RULES, SNOW_RULES, WIND_RULES, level_for


def classify(sample: WeatherSample, load_lb: float) -> RiskResult:
    by_factor: dict[str, RiskLevel] = {
        "wind": level_for(WIND_RULES, sample.wind_mph),
        "rain": level_for(RAIN_RULES, sample.rain_in_hr),
        "snow": level_for(SNOW_RULES, sample.snow_in_hr),
    }
    factor, level = max(by_factor.items(), key=lambda kv: kv[1])

    for rule in LOAD_RULES:  # data, not if-chains
        wind_in_band = rule.wind_min <= sample.wind_mph <= rule.wind_max
        load_over = load_lb > rule.load_lb_min
        if wind_in_band and load_over and rule.level > level:
            factor, level = "load_rule", rule.level

    return RiskResult(level=level, driver=factor)
