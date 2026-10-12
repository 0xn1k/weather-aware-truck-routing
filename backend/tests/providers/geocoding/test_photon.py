import httpx
import pytest
import respx

from providers.errors import ProviderError
from providers.geocoding.photon import PhotonGeocodingProvider

BASE_URL = "https://photon.komoot.io"


def feature(name, lon, lat, state=None, country=None):
    props = {"name": name}
    if state:
        props["state"] = state
    if country:
        props["country"] = country
    return {"geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props}


@respx.mock
def test_parses_label_and_context():
    response = {
        "features": [
            feature("Kansas City", -94.5786, 39.0997, state="Missouri", country="United States")
        ]
    }
    respx.get(f"{BASE_URL}/api/").mock(return_value=httpx.Response(200, json=response))
    provider = PhotonGeocodingProvider(base_url=BASE_URL)

    places = provider.search("Kansas City")

    assert len(places) == 1
    place = places[0]
    assert place.label == "Kansas City"
    assert place.context == "Missouri, United States"
    assert place.lat == 39.0997
    assert place.lon == -94.5786


@respx.mock
def test_multiple_results_preserve_order():
    response = {
        "features": [
            feature("Kansas City", -94.5786, 39.0997, state="Missouri", country="United States"),
            feature("Kansas City", -94.6275, 39.1141, state="Kansas", country="United States"),
        ]
    }
    respx.get(f"{BASE_URL}/api/").mock(return_value=httpx.Response(200, json=response))
    provider = PhotonGeocodingProvider(base_url=BASE_URL)

    places = provider.search("Kansas City")

    assert places[0].context == "Missouri, United States"
    assert places[1].context == "Kansas, United States"


@respx.mock
def test_missing_state_falls_back_to_country_only_context():
    response = {"features": [feature("Toronto", -79.3832, 43.6532, country="Canada")]}
    respx.get(f"{BASE_URL}/api/").mock(return_value=httpx.Response(200, json=response))
    provider = PhotonGeocodingProvider(base_url=BASE_URL)

    places = provider.search("Toronto")

    assert places[0].context == "Canada"


@respx.mock
def test_sends_query_and_limit_params():
    route_mock = respx.get(f"{BASE_URL}/api/").mock(
        return_value=httpx.Response(200, json={"features": []})
    )
    provider = PhotonGeocodingProvider(base_url=BASE_URL)

    provider.search("Denver", limit=3)

    sent = route_mock.calls.last.request.url.params
    assert sent["q"] == "Denver"
    assert sent["limit"] == "3"


@respx.mock
def test_spaces_are_encoded_as_percent20_not_plus():
    # httpx's params=dict encodes spaces as "+"; Photon's server returns
    # 403 Forbidden for that encoding (confirmed against the real API, not
    # a guess) but accepts %20. Checking the raw URL, not .params, since
    # httpx's parsed .params would normalize either encoding back to a
    # space and hide a regression here.
    route_mock = respx.get(f"{BASE_URL}/api/").mock(
        return_value=httpx.Response(200, json={"features": []})
    )
    provider = PhotonGeocodingProvider(base_url=BASE_URL)

    provider.search("Kansas City")

    raw_url = str(route_mock.calls.last.request.url)
    assert "Kansas%20City" in raw_url
    assert "+" not in raw_url


def test_blank_query_returns_empty_list_without_a_network_call():
    provider = PhotonGeocodingProvider(base_url=BASE_URL)
    assert provider.search("   ") == []


@respx.mock
def test_server_error_raises_provider_error_after_retries():
    route_mock = respx.get(f"{BASE_URL}/api/").mock(return_value=httpx.Response(500))
    provider = PhotonGeocodingProvider(base_url=BASE_URL, retries=2, timeout_s=1.0)

    with pytest.raises(ProviderError):
        provider.search("Denver")

    assert route_mock.call_count == 3
