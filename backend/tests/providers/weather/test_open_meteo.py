from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from core.models import Coordinate
from providers.errors import ProviderError
from providers.weather.open_meteo import OpenMeteoWeatherProvider

BASE_URL = "https://api.open-meteo.com"
START = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC)
CHICAGO = Coordinate(lat=41.8781, lon=-87.6298)
DENVER = Coordinate(lat=39.7392, lon=-104.9903)


def location(wind, gust, rain, showers, snowfall, snow_unit="inch", n_hours=3):
    return {
        "latitude": 0,
        "longitude": 0,
        "hourly_units": {"snowfall": snow_unit},
        "hourly": {
            "time": [f"2026-01-01T{6 + i:02d}:00" for i in range(n_hours)],
            "wind_speed_10m": wind,
            "wind_gusts_10m": gust,
            "rain": rain,
            "showers": showers,
            "snowfall": snowfall,
        },
    }


@respx.mock
def test_wind_and_gust_pass_through_directly():
    response = [location([12.3, 14.1, 10.0], [18.0, 20.5, 15.0], [0, 0, 0], [0, 0, 0], [0, 0, 0])]
    respx.get(f"{BASE_URL}/v1/forecast").mock(return_value=httpx.Response(200, json=response))
    provider = OpenMeteoWeatherProvider(base_url=BASE_URL)

    result = provider.hourly([CHICAGO], START, hours=3)

    samples = result[CHICAGO]
    assert [s.wind_mph for s in samples] == [12.3, 14.1, 10.0]
    assert [s.gust_mph for s in samples] == [18.0, 20.5, 15.0]


@respx.mock
def test_rain_is_rain_plus_showers():
    response = [
        location(
            [0, 0, 0],
            [0, 0, 0],
            rain=[0.02, 0.0, 0.10],
            showers=[0.0, 0.05, 0.03],
            snowfall=[0, 0, 0],
        )
    ]
    respx.get(f"{BASE_URL}/v1/forecast").mock(return_value=httpx.Response(200, json=response))
    provider = OpenMeteoWeatherProvider(base_url=BASE_URL)

    result = provider.hourly([CHICAGO], START, hours=3)

    rain_values = [s.rain_in_hr for s in result[CHICAGO]]
    assert rain_values == pytest.approx([0.02, 0.05, 0.13])


@respx.mock
def test_snow_converted_from_cm_to_inches_when_unit_says_cm():
    response = [
        location([0, 0], [0, 0], [0, 0], [0, 0], snowfall=[2.54, 5.08], snow_unit="cm", n_hours=2)
    ]
    respx.get(f"{BASE_URL}/v1/forecast").mock(return_value=httpx.Response(200, json=response))
    provider = OpenMeteoWeatherProvider(base_url=BASE_URL)

    result = provider.hourly([CHICAGO], START, hours=2)

    snow_values = [s.snow_in_hr for s in result[CHICAGO]]
    assert snow_values == pytest.approx([1.0, 2.0])


@respx.mock
def test_snow_not_converted_when_unit_already_says_inch():
    response = [
        location([0, 0], [0, 0], [0, 0], [0, 0], snowfall=[1.0, 2.0], snow_unit="inch", n_hours=2)
    ]
    respx.get(f"{BASE_URL}/v1/forecast").mock(return_value=httpx.Response(200, json=response))
    provider = OpenMeteoWeatherProvider(base_url=BASE_URL)

    result = provider.hourly([CHICAGO], START, hours=2)

    snow_values = [s.snow_in_hr for s in result[CHICAGO]]
    assert snow_values == pytest.approx([1.0, 2.0])


@respx.mock
def test_multiple_points_map_back_in_request_order():
    response = [
        location([10, 10, 10], [10, 10, 10], [0, 0, 0], [0, 0, 0], [0, 0, 0]),
        location([99, 99, 99], [99, 99, 99], [0, 0, 0], [0, 0, 0], [0, 0, 0]),
    ]
    respx.get(f"{BASE_URL}/v1/forecast").mock(return_value=httpx.Response(200, json=response))
    provider = OpenMeteoWeatherProvider(base_url=BASE_URL)

    result = provider.hourly([CHICAGO, DENVER], START, hours=3)

    assert result[CHICAGO][0].wind_mph == 10
    assert result[DENVER][0].wind_mph == 99


@respx.mock
def test_single_location_response_not_wrapped_in_a_list_is_handled():
    # plain dict, not a list
    response = location([5, 5, 5], [5, 5, 5], [0, 0, 0], [0, 0, 0], [0, 0, 0])
    respx.get(f"{BASE_URL}/v1/forecast").mock(return_value=httpx.Response(200, json=response))
    provider = OpenMeteoWeatherProvider(base_url=BASE_URL)

    result = provider.hourly([CHICAGO], START, hours=3)

    assert result[CHICAGO][0].wind_mph == 5


def test_empty_points_returns_empty_dict_without_a_network_call():
    provider = OpenMeteoWeatherProvider(base_url=BASE_URL)
    assert provider.hourly([], START, hours=49) == {}


@respx.mock
def test_request_params_use_the_designed_units_and_window():
    response = [location([0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0])]
    route_mock = respx.get(f"{BASE_URL}/v1/forecast").mock(
        return_value=httpx.Response(200, json=response)
    )
    provider = OpenMeteoWeatherProvider(base_url=BASE_URL)

    provider.hourly([CHICAGO], START, hours=3)

    sent_url = route_mock.calls.last.request.url
    query = parse_qs(urlparse(str(sent_url)).query)
    assert query["wind_speed_unit"] == ["mph"]
    assert query["precipitation_unit"] == ["inch"]
    assert query["timezone"] == ["GMT"]
    assert query["latitude"] == ["41.8781"]
    assert query["longitude"] == ["-87.6298"]
    assert query["start_hour"] == ["2026-01-01T06:00"]
    assert query["end_hour"] == ["2026-01-01T08:00"]  # start + (hours - 1)


@respx.mock
def test_server_error_raises_provider_error_after_retries():
    route_mock = respx.get(f"{BASE_URL}/v1/forecast").mock(return_value=httpx.Response(500))
    provider = OpenMeteoWeatherProvider(base_url=BASE_URL, retries=2, timeout_s=1.0)

    with pytest.raises(ProviderError):
        provider.hourly([CHICAGO], START, hours=3)

    assert route_mock.call_count == 3


@respx.mock
def test_rate_limit_gets_a_friendly_message_not_the_raw_request_url():
    # Regression test: the raw httpx exception (the full request URL, every
    # lat/lon in the batch, Open-Meteo's own error text) was surfacing
    # verbatim in the API error response and the UI.
    respx.get(f"{BASE_URL}/v1/forecast").mock(return_value=httpx.Response(429))
    provider = OpenMeteoWeatherProvider(base_url=BASE_URL, retries=1, timeout_s=1.0)

    with pytest.raises(ProviderError) as exc_info:
        provider.hourly([CHICAGO], START, hours=3)

    message = str(exc_info.value)
    assert "latitude" not in message
    assert "rate-limited" in message
