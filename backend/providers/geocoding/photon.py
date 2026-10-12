from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

import httpx

from core.models import Place
from providers.errors import ProviderError
from providers.http import DEFAULT_HEADERS


class PhotonGeocodingProvider:
    """Backs the /api/geocode proxy and the frontend's place autocomplete
    (backend/README.md Section 2)."""

    def __init__(self, base_url: str, timeout_s: float = 10.0, retries: int = 2):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.retries = retries

    def search(self, query: str, limit: int = 5) -> list[Place]:
        if not query.strip():
            return []
        data = self._get({"q": query, "limit": str(limit)})
        return [self._parse_feature(f) for f in data.get("features", [])]

    def _get(self, params: dict[str, str]) -> dict[str, Any]:
        # httpx's params=dict encodes spaces as "+" (form-encoding style).
        # Photon's server rejects "+"-encoded queries with 403 Forbidden —
        # confirmed by direct testing, not a guess — so the query string is
        # built manually here with %20 encoding instead.
        query_string = urlencode(params, quote_via=quote)
        url = f"{self.base_url}/api/?{query_string}"
        last_error: Exception | None = None
        for _attempt in range(self.retries + 1):
            try:
                response = httpx.get(url, headers=DEFAULT_HEADERS, timeout=self.timeout_s)
                response.raise_for_status()
                result: dict[str, Any] = response.json()
                return result
            except httpx.HTTPError as exc:
                last_error = exc
        raise ProviderError(
            f"Photon request failed after {self.retries + 1} attempts: {last_error}"
        )

    @staticmethod
    def _parse_feature(feature: dict[str, Any]) -> Place:
        lon, lat = feature["geometry"]["coordinates"]
        props = feature.get("properties", {})
        label = props.get("name", "")
        context = ", ".join(p for p in (props.get("state"), props.get("country")) if p)
        return Place(lat=lat, lon=lon, label=label, context=context)
