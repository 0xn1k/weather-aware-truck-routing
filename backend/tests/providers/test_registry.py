import pytest

import providers.registry as registry
from providers.geocoding.photon import PhotonGeocodingProvider
from providers.registry import (
    build_geocoding_provider,
    build_routing_provider,
    build_weather_provider,
    get_weather_provider_name,
    set_weather_provider_name,
)
from providers.routing.fallback import FallbackRoutingProvider
from providers.routing.valhalla import ValhallaRoutingProvider
from providers.weather.fake import FakeWeatherProvider
from providers.weather.open_meteo import OpenMeteoWeatherProvider


@pytest.fixture(autouse=True)
def _reset_weather_provider_override():
    # set_weather_provider_name mutates module-level state (by design — see
    # its docstring) so it survives across requests without a redeploy.
    # That same persistence would leak between tests if left alone.
    yield
    registry._weather_provider_override = None


def test_build_routing_provider_wraps_valhalla_primary_and_fallback(settings):
    settings.ROUTING_PROVIDER = "valhalla"
    settings.ROUTING_PRIMARY_URL = "https://api.stadiamaps.com"
    settings.ROUTING_FALLBACK_URL = "https://valhalla1.openstreetmap.de"
    settings.STADIA_API_KEY = "test-key"

    provider = build_routing_provider()

    assert isinstance(provider, FallbackRoutingProvider)
    assert isinstance(provider.primary, ValhallaRoutingProvider)
    assert isinstance(provider.secondary, ValhallaRoutingProvider)
    assert provider.primary.base_url == "https://api.stadiamaps.com"
    assert provider.primary.api_key == "test-key"
    assert provider.secondary.base_url == "https://valhalla1.openstreetmap.de"
    assert provider.secondary.api_key == ""  # fallback never gets the Stadia key


def test_build_routing_provider_rejects_unknown_provider(settings):
    settings.ROUTING_PROVIDER = "osrm"

    with pytest.raises(ValueError, match="osrm"):
        build_routing_provider()


def test_build_weather_provider_returns_open_meteo(settings):
    settings.WEATHER_PROVIDER = "open_meteo"

    provider = build_weather_provider()

    assert isinstance(provider, OpenMeteoWeatherProvider)


def test_build_weather_provider_returns_fake(settings):
    settings.WEATHER_PROVIDER = "fake"

    provider = build_weather_provider()

    assert isinstance(provider, FakeWeatherProvider)


def test_build_weather_provider_rejects_unknown_provider(settings):
    settings.WEATHER_PROVIDER = "accuweather"

    with pytest.raises(ValueError, match="accuweather"):
        build_weather_provider()


def test_weather_provider_name_defaults_to_the_setting(settings):
    settings.WEATHER_PROVIDER = "open_meteo"

    assert get_weather_provider_name() == "open_meteo"


def test_set_weather_provider_name_overrides_the_setting(settings):
    settings.WEATHER_PROVIDER = "open_meteo"

    set_weather_provider_name("fake")

    assert get_weather_provider_name() == "fake"
    assert isinstance(build_weather_provider(), FakeWeatherProvider)


def test_set_weather_provider_name_rejects_unknown_value():
    with pytest.raises(ValueError, match="accuweather"):
        set_weather_provider_name("accuweather")


def test_build_geocoding_provider_uses_geocoder_url_setting(settings):
    settings.GEOCODER_URL = "https://photon.komoot.io"

    provider = build_geocoding_provider()

    assert isinstance(provider, PhotonGeocodingProvider)
    assert provider.base_url == "https://photon.komoot.io"
