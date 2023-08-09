"""Tests for Audiobookshelf api."""
import asyncio
from collections.abc import Coroutine
from typing import Any

import aiohttp
from _pytest.logging import LogCaptureFixture
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.audiobookshelf.api import (
    AudiobookshelfApiClient,
)


async def test_api(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: LogCaptureFixture,
) -> Coroutine[Any, Any, None]:
    """Test API calls."""

    # To test the api submodule, we first create an instance of our API client
    api = AudiobookshelfApiClient(
        host="some_host",
        access_token="some_access_token",
        session=async_get_clientsession(hass),
    )

    # Use aioclient_mock which is provided by `pytest_homeassistant_custom_components`
    # to mock responses to aiohttp requests. In this case we are telling the mock to
    # return {"test": "test"} when a `GET` call is made to the specified URL. We then
    # call `async_get_data` which will make that `GET` request.
    # aioclient_mock.get("host", json={"test": "test"})
    # assert await api.async_get_data() == {"test": "test"}

    # We do the same for `async_set_title`. Note the difference in the mock call
    # between the previous step and this one. We use `patch` here instead of `get`
    # because we know that `async_set_title` calls `api_wrapper` with `patch` as the
    # first parameter
    # aioclient_mock.patch("host")
    # assert await api.async_set_title("test") is None

    # In order to get 100% coverage, we need to test `api_wrapper` to test the code
    # that isn't already called by `async_get_data` and `async_set_title`. Because the
    # only logic that lives inside `api_wrapper` that is not being handled by a third
    # party library (aiohttp) is the exception handling, we also want to simulate
    # raising the exceptions to ensure that the function handles them as expected.
    # The caplog fixture allows access to log messages in tests. This is particularly
    # useful during exception handling testing since often the only action as part of
    # exception handling is a logging statement
    caplog.clear()
    aioclient_mock.put("some_host", exc=asyncio.TimeoutError)
    assert await api.api_wrapper("put", "some_host") is None
    assert (
        len(caplog.record_tuples) == 1
        and "Timeout error fetching information from" in caplog.record_tuples[0][2]
    )

    caplog.clear()
    aioclient_mock.post("some_host", exc=aiohttp.ClientError)
    assert await api.api_wrapper("post", "some_host") is None
    assert (
        len(caplog.record_tuples) == 1
        and "Error fetching information from" in caplog.record_tuples[0][2]
    )

    caplog.clear()
    aioclient_mock.post("some_host/2", exc=Exception)
    assert await api.api_wrapper("post", "some_host/2") is None
    assert (
        len(caplog.record_tuples) == 1
        and "Something really wrong happened!" in caplog.record_tuples[0][2]
    )

    caplog.clear()
    aioclient_mock.post("some_host/3", exc=TypeError)
    assert await api.api_wrapper("post", "some_host/3") is None
    assert (
        len(caplog.record_tuples) == 1
        and "Error parsing information from" in caplog.record_tuples[0][2]
    )
