from __future__ import annotations

from datetime import datetime
from typing import Protocol

from core.models import Coordinate, WeatherSample


class WeatherProvider(Protocol):
    def hourly(
        self, points: list[Coordinate], start: datetime, hours: int
    ) -> dict[Coordinate, list[WeatherSample]]: ...
