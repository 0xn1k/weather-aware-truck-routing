from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


@dataclass(frozen=True)
class Coordinate:
    lat: float
    lon: float


@dataclass(frozen=True)
class Place:
    """One geocoding search result — origin/destination autocomplete."""

    lat: float
    lon: float
    label: str  # e.g. "Kansas City"
    context: str = ""  # e.g. "Missouri, United States"


@dataclass(frozen=True)
class WeatherSample:
    wind_mph: float
    gust_mph: float
    rain_in_hr: float
    snow_in_hr: float


@dataclass(frozen=True)
class RiskResult:
    level: RiskLevel
    driver: str  # "wind" | "rain" | "snow" | "load_rule"


@dataclass(frozen=True)
class CheckpointPlan:
    """A checkpoint's position and timing, before weather is attached.
    sampling.py produces these; the weather fetch + classify() step
    (services/weather_service.py, Phase 4) turns each one into a Checkpoint."""

    position: Coordinate
    mile_marker: float
    segment_miles: float
    eta: datetime  # UTC
    place: str = ""


@dataclass(frozen=True)
class Maneuver:
    """One routing-engine maneuver: `time_s` spread across the geometry
    points from `begin_shape_index` to `end_shape_index`, in proportion to
    the distance each point covers (backend/README.md Section 5.2)."""

    time_s: float
    begin_shape_index: int
    end_shape_index: int


@dataclass(frozen=True)
class Checkpoint:
    position: Coordinate
    mile_marker: float
    segment_miles: float
    eta: datetime  # UTC
    weather: WeatherSample
    risk: RiskResult
    place: str = ""


@dataclass(frozen=True)
class Vehicle:
    """The truck being routed. Kept in raw pounds rather than pre-converted
    to any provider's unit (e.g. Valhalla wants metric tons) — each
    RoutingProvider converts units itself, so this stays provider-agnostic."""

    load_lb: float
    empty_weight_lb: float

    @property
    def total_weight_lb(self) -> float:
        return self.load_lb + self.empty_weight_lb


@dataclass(frozen=True)
class Route:
    id: str
    label: str
    geometry: list[Coordinate]
    distance_mi: float
    duration_s: int
    maneuvers: list[Maneuver] = field(default_factory=list)
    cumulative_miles: list[float] = field(default_factory=list)
    cumulative_seconds: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class PeakReading:
    checkpoint: Checkpoint
    value: float


@dataclass(frozen=True)
class RouteSummary:
    miles_by_level: dict[RiskLevel, float]
    avg_risk: float
    max_level: RiskLevel
    worst_checkpoint: Checkpoint
    peak_wind: PeakReading
    peak_rain: PeakReading
    peak_snow: PeakReading
    duration_s: int
