from __future__ import annotations

import random
from datetime import datetime

from core.geo import haversine
from core.models import Coordinate, WeatherSample

# (wind_mph range, rain_in_hr range) per tier — Low, Moderate, High, Severe.
# Each range sits comfortably inside its risk band (core/risk/rules.py), not
# right at a boundary, and a seeded random draw (see _sample) picks a point
# inside it so two different (location, hour) samples at the same tier
# don't come back as the exact same suspiciously-round number. High/Severe
# are driven by rain rather than wind: the 35-54 mph wind band is also what
# core/risk/rules.py's LOAD_RULES escalates (wind 45-54 + load over 30,000
# lb -> No travel, regardless of the plain wind-only classification) — any
# real truck's default load would silently turn a wind-driven "Severe"
# sample into "No travel" here too. Rain isn't touched by LOAD_RULES, so it
# reliably stays at the level requested.
#
# No Travel is deliberately NOT in this cyclic pattern. Each route samples
# ~40+ checkpoints, each at a different (location, hour) — even a small
# per-sample chance of landing on No Travel compounds across that many
# independent draws into a near-certainty for every route on every trip,
# which is exactly what happened with an earlier version of this pattern
# (every single plan showed "Do not travel at this departure time"). No
# Travel is instead a single, deliberately-placed storm cell below, so it's
# reliably reachable for testing without dominating every result.
_TIER_RANGES = [
    ((3.0, 15.0), (0.0, 0.0)),  # Low
    ((25.0, 33.0), (0.0, 0.0)),  # Moderate
    ((0.0, 0.0), (0.26, 0.48)),  # High
    ((0.0, 0.0), (0.52, 0.95)),  # Severe
]
_NO_TRAVEL_WIND_RANGE = (56.0, 70.0)
# Mostly calm with occasional spikes up through every tier, repeating every
# 20 hours — shifted per point (see _phase) so a "system" appears to move
# across the map as the forecast slider advances, instead of every point
# spiking at once.
_PATTERN = [0, 0, 0, 1, 0, 0, 1, 2, 1, 0, 0, 1, 3, 2, 1, 0, 0, 2, 2, 0]

# A single, fixed storm cell — not reachable by the cyclic pattern above —
# so No Travel is reliably testable (route something through the Billings,
# MT area) without ever being a near-certainty for an arbitrary trip.
# Deliberately NOT on any of the 3 built-in "Try an example" corridors
# (frontend/src/features/trip-form/TryExamples.tsx: Chicago-Denver follows
# I-80 through Iowa/Nebraska; Dallas-OKC and Salt Lake City-Denver stay
# well south of here too) — an earlier version of this cell sat on the
# Chicago-Denver corridor and made that one specific, heavily-used example
# always blocked. Active for all 49 hours, not just a window — tying it to
# a specific ETA window too would make it depend on guessing a route's
# exact timing/speed to ever actually land inside it; geography alone is
# reliable regardless of departure time, load, or which of the 3 routes
# gets taken.
_STORM_CENTER = Coordinate(lat=45.8, lon=-108.5)  # Billings, MT
_STORM_RADIUS_MI = 60.0


class FakeWeatherProvider:
    """Deterministic synthetic weather — no network call, no rate limit.
    Enabled via WEATHER_PROVIDER=fake (backend/README.md Section 3). Always
    produces a believable mix of Low/Moderate/High/Severe somewhere along
    any route/corridor, plus a single reliably-reachable No Travel storm
    cell (see _STORM_CENTER) — real weather on a given day may not offer
    any of that, making this useful for demos and for testing the
    risk/heatmap UI on demand."""

    def hourly(
        self, points: list[Coordinate], start: datetime, hours: int
    ) -> dict[Coordinate, list[WeatherSample]]:
        return {point: self._series(point, hours) for point in points}

    def _series(self, point: Coordinate, hours: int) -> list[WeatherSample]:
        phase = _phase(point)
        in_storm_cell = haversine(point, _STORM_CENTER) <= _STORM_RADIUS_MI
        return [self._sample(point, hour, phase, in_storm_cell) for hour in range(hours)]

    def _sample(
        self, point: Coordinate, hour: int, phase: int, in_storm_cell: bool
    ) -> WeatherSample:
        # Seeded by (location, hour) — same trip re-requested (a repeated
        # demo, a test re-run) gets the same weather every time, but two
        # different points or hours don't come back with the exact same
        # suspiciously-round number the old fixed-per-tier values did.
        seed = hash((round(point.lat, 2), round(point.lon, 2), hour))
        rng = random.Random(seed)
        wind_range = _NO_TRAVEL_WIND_RANGE if in_storm_cell else _TIER_RANGES[_tier(hour, phase)][0]
        rain_range = (0.0, 0.0) if in_storm_cell else _TIER_RANGES[_tier(hour, phase)][1]
        wind = rng.uniform(*wind_range)
        rain = rng.uniform(*rain_range)
        gust = wind * rng.uniform(1.1, 1.3)
        return WeatherSample(wind_mph=wind, gust_mph=gust, rain_in_hr=rain, snow_in_hr=0.0)


def _tier(hour: int, phase: int) -> int:
    return _PATTERN[(hour + phase) % len(_PATTERN)]


def _phase(point: Coordinate) -> int:
    # Deterministic per-location offset so different points peak at
    # different hours rather than all moving in lockstep.
    return int(round(point.lat, 1) * 10 + round(point.lon, 1) * 10) % len(_PATTERN)
