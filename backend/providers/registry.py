from __future__ import annotations

from django.conf import settings

from providers.geocoding.base import GeocodingProvider
from providers.geocoding.photon import PhotonGeocodingProvider
from providers.routing.base import RoutingProvider
from providers.routing.fallback import FallbackRoutingProvider
from providers.routing.valhalla import ValhallaRoutingProvider
from providers.weather.base import WeatherProvider
from providers.weather.fake import FakeWeatherProvider
from providers.weather.open_meteo import OpenMeteoWeatherProvider


def build_routing_provider() -> RoutingProvider:
    """Services ask for a RoutingProvider here — never import
    ValhallaRoutingProvider directly — so swapping engines is a settings
    change, not a rewrite (backend/README.md Section 2)."""
    if settings.ROUTING_PROVIDER != "valhalla":
        raise ValueError(f"Unknown ROUTING_PROVIDER: {settings.ROUTING_PROVIDER!r}")
    primary = ValhallaRoutingProvider(
        base_url=settings.ROUTING_PRIMARY_URL, api_key=settings.STADIA_API_KEY
    )
    secondary = ValhallaRoutingProvider(base_url=settings.ROUTING_FALLBACK_URL)
    return FallbackRoutingProvider(primary, secondary)


WEATHER_PROVIDER_NAMES = ("fake", "open_meteo")

# Overrides settings.WEATHER_PROVIDER at runtime — the frontend's header
# toggle (apps/trips/views.py's WeatherProviderView) flips this instead of
# requiring an env var change + redeploy. None means "use the env var's
# value", which is also what every fresh process starts as. This is
# module-level, process-global state: one gunicorn worker (this backend
# runs with the default single worker — see backend/railway.json /
# render.yaml's startCommand) shares it across every request it handles,
# and it resets back to the env var on the next deploy/restart. Fine for a
# single-person demo deployment; a real multi-tenant service would need
# this to be per-request/per-session instead, not a shared global.
_weather_provider_override: str | None = None


def get_weather_provider_name() -> str:
    return _weather_provider_override or settings.WEATHER_PROVIDER


def set_weather_provider_name(name: str) -> None:
    if name not in WEATHER_PROVIDER_NAMES:
        raise ValueError(f"Unknown WEATHER_PROVIDER: {name!r}")
    global _weather_provider_override
    _weather_provider_override = name


def build_weather_provider() -> WeatherProvider:
    name = get_weather_provider_name()
    if name == "fake":
        # No network call, no rate limit — for demos and local testing when
        # the real provider's quota is exhausted or real weather is too calm
        # to exercise the risk/heatmap UI (providers/weather/fake.py).
        return FakeWeatherProvider()
    if name != "open_meteo":
        raise ValueError(f"Unknown WEATHER_PROVIDER: {name!r}")
    return OpenMeteoWeatherProvider()


def build_geocoding_provider() -> GeocodingProvider:
    return PhotonGeocodingProvider(base_url=settings.GEOCODER_URL)
