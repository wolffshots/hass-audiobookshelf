"""Tests for Audiobookshelf api."""
import asyncio

import aiohttp
import pytest
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
) -> None:
    """Test API calls."""

    # To test the api submodule, we first create an instance of our API client
    api = AudiobookshelfApiClient(
        host="some_host",
        access_token="some_access_token",
        session=async_get_clientsession(hass),
    )

    caplog.clear()
    aioclient_mock.clear_requests()
    aioclient_mock.get("some_host", exc=asyncio.TimeoutError)
    assert await api.api_wrapper("get", "some_host") is None
    assert (
        len(caplog.record_tuples) == 1
        and "Timeout error fetching information from" in caplog.record_tuples[0][2]
    )

    caplog.clear()
    aioclient_mock.clear_requests()
    aioclient_mock.get("some_host", json={"test": "test"})
    assert (await api.api_wrapper("get", "some_host")) == {"test": "test"}
    assert len(caplog.record_tuples) == 0

    caplog.clear()
    aioclient_mock.clear_requests()
    aioclient_mock.put("some_host", exc=asyncio.TimeoutError)
    assert await api.api_wrapper("put", "some_host") is None
    assert (
        len(caplog.record_tuples) == 1
        and "Timeout error fetching information from" in caplog.record_tuples[0][2]
    )

    caplog.clear()
    aioclient_mock.clear_requests()
    aioclient_mock.patch("some_host", exc=asyncio.TimeoutError)
    assert await api.api_wrapper("patch", "some_host") is None
    assert (
        len(caplog.record_tuples) == 1
        and "Timeout error fetching information from" in caplog.record_tuples[0][2]
    )

    caplog.clear()
    aioclient_mock.clear_requests()
    aioclient_mock.post("some_host", exc=aiohttp.ClientError)
    assert await api.api_wrapper("post", "some_host") is None
    assert (
        len(caplog.record_tuples) == 1
        and "Error fetching information from" in caplog.record_tuples[0][2]
    )

    caplog.clear()
    aioclient_mock.clear_requests()
    aioclient_mock.post("some_host/2", exc=Exception)
    with pytest.raises(Exception) as e_info:
        assert await api.api_wrapper("post", "some_host/2")
        assert e_info.errisinstance(Exception)
    assert (
        len(caplog.record_tuples) == 1
        and "Something really wrong happened!" in caplog.record_tuples[0][2]
    )

    caplog.clear()
    aioclient_mock.clear_requests()
    aioclient_mock.post("some_host/3", exc=TypeError)
    with pytest.raises(Exception) as e_info:
        assert await api.api_wrapper("post", "some_host/3") is None
        assert e_info.errisinstance(Exception)
    assert (
        len(caplog.record_tuples) == 1
        and "Error parsing information from" in caplog.record_tuples[0][2]
    )

    caplog.clear()
    aioclient_mock.clear_requests()
    aioclient_mock.put("some_host", exc=asyncio.TimeoutError)
    assert (
        await api.api_wrapper(
            method="put",
            url="some_host",
            headers={"Test": "test header"},
        )
        is None
    )
    assert (
        len(caplog.record_tuples) == 1
        and "Timeout error fetching information from" in caplog.record_tuples[0][2]
    )


async def test_api_helpers(
    hass: HomeAssistant,
    caplog: LogCaptureFixture,
) -> None:
    """Test the functions that extract data from API responses"""
    caplog.clear()
    api = AudiobookshelfApiClient(
        host="some_host",
        access_token="some_access_token",
        session=async_get_clientsession(hass),
    )
    data = {"openSessions": [], "users": []}
    assert api.count_open_sessions(data) == 0
    assert api.count_active_users(data) == 0
    data = {
        "openSessions": [
            {
                "bookId": "testing_session_1",
                "chapters": "testing_session_1",
                "coverPath": "testing_session_1",
                "currentTime": "testing_session_1",
                "date": "testing_session_1",
                "dayOfWeek": "testing_session_1",
                "deviceInfo": "testing_session_1",
                "displayAuthor": "testing_session_1",
                "displayTitle": "testing_session_1",
                "duration": "testing_session_1",
                "episodeId": "testing_session_1",
                "id": "testing_session_1",
                "libraryId": "testing_session_1",
                "libraryItemId": "testing_session_1",
                "mediaMetadata": "testing_session_1",
                "mediaPlayer": "testing_session_1",
                "mediaType": "testing_session_1",
                "playMethod": "testing_session_1",
                "serverVersion": "testing_session_1",
                "startTime": "testing_session_1",
                "startedAt": "testing_session_1",
                "timeListening": "testing_session_1",
                "updatedAt": "testing_session_1",
                "userId": "testing_session_1",
            },
        ],
        "users": [
            {
                "createdAt": "testing_user_1",
                "id": "testing_user_1",
                "isActive": True,
                "isLocked": "testing_user_1",
                "itemTagsSelected": "testing_user_1",
                "lastSeen": "testing_user_1",
                "librariesAccessible": "testing_user_1",
                "oldUserId": "testing_user_1",
                "permissions": "testing_user_1",
                "seriesHideFromContinueListening": "testing_user_1",
                "token": "testing_user_1",
                "type": "testing_user_1",
                "username": "testing_user_1",
            },
            {
                "createdAt": "testing_user_2",
                "id": "testing_user_2",
                "isActive": False,
                "isLocked": "testing_user_2",
                "itemTagsSelected": "testing_user_2",
                "lastSeen": "testing_user_2",
                "librariesAccessible": "testing_user_2",
                "oldUserId": "testing_user_2",
                "permissions": "testing_user_2",
                "seriesHideFromContinueListening": "testing_user_2",
                "token": "testing_user_2",
                "type": "testing_user_2",
                "username": "testing_user_2",
            },
            {
                "createdAt": "testing_user_3",
                "id": "testing_user_3",
                "isActive": True,
                "isLocked": "testing_user_3",
                "itemTagsSelected": "testing_user_3",
                "lastSeen": "testing_user_3",
                "librariesAccessible": "testing_user_3",
                "oldUserId": "testing_user_3",
                "permissions": "testing_user_3",
                "seriesHideFromContinueListening": "testing_user_3",
                "token": "some_access_token",
                "type": "testing_user_3",
                "username": "testing_user_3",
            },
            {
                "createdAt": "testing_user_4",
                "id": "testing_user_4",
                "isActive": True,
                "isLocked": "testing_user_4",
                "itemTagsSelected": "testing_user_4",
                "lastSeen": "testing_user_4",
                "librariesAccessible": "testing_user_4",
                "oldUserId": "testing_user_4",
                "permissions": "testing_user_4",
                "seriesHideFromContinueListening": "testing_user_4",
                "token": "testing_user_4",
                "type": "testing_user_4",
                "username": "hass",
            },
        ],
    }
    assert api.count_open_sessions(data) == 1
    assert api.count_active_users(data) == 1

    caplog.clear()
    assert api.get_host() == "some_host"
