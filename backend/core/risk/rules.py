from __future__ import annotations

from dataclasses import dataclass

from core.models import RiskLevel


@dataclass(frozen=True)
class Threshold:
    min_value: float  # inclusive lower bound for this level
    level: RiskLevel


def level_for(rules: list[Threshold], value: float) -> RiskLevel:
    level = rules[0].level
    for rule in rules:
        if value >= rule.min_value:
            level = rule.level
    return level


# A shared boundary value belongs to the higher level; "severe" bounds that
# read as "> 1.00" etc. in the brief are expressed as the NO_TRAVEL row's
# min_value sitting just above that figure (see backend/README.md Section 5.4
# and the top-level README's Section 12, decision #1).
WIND_RULES: list[Threshold] = [
    Threshold(0, RiskLevel.LOW),
    Threshold(25, RiskLevel.MODERATE),
    Threshold(35, RiskLevel.HIGH),
    Threshold(45, RiskLevel.SEVERE),
    Threshold(55, RiskLevel.NO_TRAVEL),
]

RAIN_RULES: list[Threshold] = [
    Threshold(0.00, RiskLevel.LOW),
    Threshold(0.10, RiskLevel.MODERATE),
    Threshold(0.25, RiskLevel.HIGH),
    Threshold(0.50, RiskLevel.SEVERE),
    # Brief says NO_TRAVEL is "> 1.00" (exclusive), not ">= 1.00". Open-Meteo
    # reports rain/snow at 2 decimal places (see providers/weather/open_meteo.py),
    # so the smallest value strictly above 1.00 at that precision is 1.01 —
    # using it as the inclusive floor here is equivalent to ">" at the data's
    # actual resolution.
    Threshold(1.01, RiskLevel.NO_TRAVEL),
]

SNOW_RULES: list[Threshold] = [
    Threshold(0.0, RiskLevel.LOW),
    Threshold(0.5, RiskLevel.MODERATE),
    Threshold(1.0, RiskLevel.HIGH),
    Threshold(2.0, RiskLevel.SEVERE),
    Threshold(3.01, RiskLevel.NO_TRAVEL),  # same reasoning: "> 3.0" at 2-decimal precision
]


@dataclass(frozen=True)
class LoadRule:
    wind_min: float
    wind_max: float  # inclusive; float("inf") for no upper bound
    load_lb_min: float  # exclusive — "over X lb"
    level: RiskLevel
    text: str


# Applied after the per-factor thresholds, and only ever raising the level
# (backend/README.md Section 5.4).
LOAD_RULES: list[LoadRule] = [
    LoadRule(55, float("inf"), 0, RiskLevel.NO_TRAVEL, "Wind ≥ 55 mph, any load → No travel"),
    LoadRule(45, 54, 30_000, RiskLevel.NO_TRAVEL, "45–54 mph and load over 30,000 lb → No travel"),
    LoadRule(35, 44, 40_000, RiskLevel.SEVERE, "35–44 mph and load over 40,000 lb → Severe"),
]
