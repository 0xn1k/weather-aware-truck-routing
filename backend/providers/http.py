"""Shared HTTP conventions for every provider adapter.

A descriptive User-Agent for the free/public servers this app calls
(Photon, the public Valhalla fallback, Open-Meteo) — top-level README.md's
own reliability section already called for this ("Public free servers get
... a descriptive User-Agent"), but no provider actually sent one. Confirmed
the gap is load-bearing, not cosmetic: Photon returns 403 Forbidden
specifically for requests whose User-Agent identifies as the `python-httpx`
library (a common anti-bot measure), which is httpx's unmodified default.
"""

USER_AGENT = "Corridor/1.0 (weather-aware truck routing demo app)"
DEFAULT_HEADERS = {"User-Agent": USER_AGENT}
