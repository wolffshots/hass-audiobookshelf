"""Tests for how the coordinator maps API failures onto Home Assistant errors."""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioaudiobookshelf.exceptions import ApiError, NotFoundError, TokenIsMissingError
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.audiobookshelf.audiobook_shelf_data_update_coordinator import (
    AudiobookShelfDataUpdateCoordinator,
)

LIBRARY_STATS = (
    b'{"totalAuthors": 1, "totalGenres": 3, "totalItems": 12, "totalSize": 1024,'
    b' "totalDuration": 60.5, "numAudioTracks": 40}'
)
OPEN_SESSIONS = b'{"sessions": []}'
USERS = b'{"users": []}'
USERS_ONLINE = b'{"usersOnline": []}'
AUTH_SESSIONS = b'{"total": 2}'


def _coordinator() -> AudiobookShelfDataUpdateCoordinator:
    """Build a coordinator with Home Assistant stubbed out."""
    with patch.object(
        AudiobookShelfDataUpdateCoordinator, "__init__", return_value=None
    ):
        coordinator = AudiobookShelfDataUpdateCoordinator(  # type: ignore[call-arg]
            MagicMock(), MagicMock(), 300, "http://abs", "token"
        )
    coordinator.api_url = "http://abs"
    coordinator.token = "api-key"  # noqa: S105
    coordinator.libraries = []
    return coordinator


def _with_client(responses: dict[str, Any]) -> AudiobookShelfDataUpdateCoordinator:
    """Return a coordinator whose client answers endpoints from a mapping."""
    coordinator = _coordinator()

    async def _get(endpoint: str) -> Any:
        """Return the mapped response, raising it instead if it is an exception."""
        response = responses[endpoint]
        if isinstance(response, Exception):
            raise response
        return response

    client = MagicMock()
    client._get = AsyncMock(side_effect=_get)  # noqa: SLF001
    # SimpleNamespace rather than MagicMock: "name" is a reserved constructor
    # argument on Mock and would not read back as an attribute.
    client.get_all_libraries = AsyncMock(
        return_value=[SimpleNamespace(id_="lib-1", name="Books")]
    )
    coordinator.get_client = AsyncMock(return_value=client)  # type: ignore[method-assign]
    return coordinator


def _endpoints(**overrides: Any) -> dict[str, Any]:
    """Build a full set of healthy endpoint responses, with optional overrides."""
    endpoints = {
        "api/users": USERS,
        "api/users/online": USERS_ONLINE,
        "api/sessions/open": OPEN_SESSIONS,
        "api/me/sessions": AUTH_SESSIONS,
        "api/libraries/lib-1/stats": LIBRARY_STATS,
    }
    endpoints.update(overrides)
    return endpoints


def test_happy_path_derives_count_libraries() -> None:
    """A healthy poll counts the libraries it gathered stats for."""
    coordinator = _with_client(_endpoints())
    data = asyncio.run(coordinator._async_update_data())  # noqa: SLF001
    assert data["count_libraries"] == 1
    assert data["count_auth_sessions"] == 2
    assert coordinator.libraries[0].name == "Books"


def test_auth_error_triggers_reauth() -> None:
    """A missing token surfaces as AbsAuthError and must prompt for reauth."""
    coordinator = _with_client(
        _endpoints(**{"api/users": TokenIsMissingError("no token")})
    )
    with pytest.raises(ConfigEntryAuthFailed):
        asyncio.run(coordinator._async_update_data())  # noqa: SLF001


def test_api_error_is_update_failed() -> None:
    """A non-auth API error must not prompt for reauth."""
    coordinator = _with_client(_endpoints(**{"api/users": ApiError("boom")}))
    with pytest.raises(UpdateFailed):
        asyncio.run(coordinator._async_update_data())  # noqa: SLF001


def test_not_found_is_update_failed_not_reauth() -> None:
    """A 404 on a required endpoint is a failure, not an auth problem."""
    coordinator = _with_client(_endpoints(**{"api/users": NotFoundError("gone")}))
    with pytest.raises(UpdateFailed):
        asyncio.run(coordinator._async_update_data())  # noqa: SLF001


def test_auth_sessions_degrade_to_none_on_404() -> None:
    """Servers older than 2.36.0 lack /api/me/sessions and must still poll."""
    coordinator = _with_client(
        _endpoints(**{"api/me/sessions": NotFoundError("no such endpoint")})
    )
    data = asyncio.run(coordinator._async_update_data())  # noqa: SLF001
    assert data["count_auth_sessions"] is None
    assert data["count_libraries"] == 1


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b'{"totalGenres": 3}', id="missing-required-field"),
        pytest.param(b'{"totalItems": null}', id="null-where-int-expected"),
        pytest.param(b"<html>not json</html>", id="non-json-body"),
    ],
)
def test_schema_drift_is_update_failed(body: bytes) -> None:
    """Parse failures are neither AbsError nor ClientError and must be caught."""
    coordinator = _with_client(_endpoints(**{"api/libraries/lib-1/stats": body}))
    with pytest.raises(UpdateFailed, match="library stats"):
        asyncio.run(coordinator._async_update_data())  # noqa: SLF001
