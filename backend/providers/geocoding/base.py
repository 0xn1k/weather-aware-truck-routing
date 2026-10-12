from __future__ import annotations

from typing import Protocol

from core.models import Place


class GeocodingProvider(Protocol):
    def search(self, query: str, limit: int = 5) -> list[Place]: ...
