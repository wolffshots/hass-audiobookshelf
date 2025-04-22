"""Module containing the data update coordinator the Audiobookshelf integration."""

import time
from dataclasses import dataclass
from datetime import timedelta
from logging import getLogger
from typing import Annotated

from aioaudiobookshelf import (
    AdminClient,
    SessionConfiguration,
    get_admin_client_by_token,
)
from aioaudiobookshelf.schema import _BaseModel
from aioaudiobookshelf.schema.library import Library
from aioaudiobookshelf.schema.session import PlaybackSession
from aioaudiobookshelf.schema.user import _UserBase
from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from mashumaro.types import Alias

_LOGGER = getLogger(__name__)

API_DATA_METHODS = [
    "count_users",
    "count_users_online",
    "count_open_sessions",
    "count_recent_sessions",
    "library_stats",
]


@dataclass(kw_only=True)
class AllUsersResponse(_BaseModel):
    """AllUsersResponse."""

    users: list[_UserBase]


@dataclass(kw_only=True)
class UsersOnlineResponse(_BaseModel):
    """UsersOnlineResponse."""

    users_online: Annotated[list[_UserBase], Alias("usersOnline")]


@dataclass(kw_only=True)
class OpenSessionsResponse(_BaseModel):
    """OpenSessionsResponse."""

    sessions: Annotated[list[PlaybackSession], Alias("sessions")]

    def filter_active_sessions(
        self, max_idle_seconds: int = 120
    ) -> list[PlaybackSession]:
        """Filter sessions that have been updated recently."""
        current_time_ms = int(time.time() * 1000)
        _LOGGER.info("Current time in ms: %s", current_time_ms)
        _LOGGER.info("Sessions: %s", self.sessions)
        return [
            session
            for session in self.sessions
            if hasattr(session, "updated_at")
            and (current_time_ms - session.updated_at) < (max_idle_seconds * 1000)
        ]


@dataclass(kw_only=True)
class LibraryStats(_BaseModel):
    """LibraryStats."""

    total_authors: Annotated[int | None, Alias("totalAuthors")] = None
    total_genres: Annotated[int, Alias("totalGenres")]
    total_items: Annotated[int, Alias("totalItems")]
    total_size: Annotated[int, Alias("totalSize")]
    total_duration: Annotated[float, Alias("totalDuration")]
    total_audio_tracks: Annotated[int, Alias("numAudioTracks")]


class AudiobookShelfDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Audiobookshelf data from the API."""

    _client: AdminClient = None  # type: ignore[import-untyped]
    api_url: str = ""

    def __init__(
        self, hass: HomeAssistant, scan_interval: int, api_url: str, token: str
    ) -> None:
        """Initialize."""
        self.api_url = api_url
        self.token = token

        super().__init__(
            hass,
            _LOGGER,
            name="audiobookshelf",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def get_client(self) -> AdminClient:
        """Get the client to interact with the API."""
        if self._client is None:
            client_session = async_get_clientsession(self.hass)
            self._client = await get_admin_client_by_token(
                session_config=SessionConfiguration(
                    session=client_session,
                    url=self.api_url,
                    logger=_LOGGER,
                    pagination_items_per_page=30,
                    token=self.token,
                ),
            )
        return self._client

    async def get_libraries(self) -> list[Library]:
        """Fetch library id list from API."""
        return await (await self.get_client()).get_all_libraries()  # type: ignore[no-any-return]

    async def count_users(self) -> int:
        """Fetch and count active users from API."""
        response_cls: type[AllUsersResponse] = AllUsersResponse
        client = await self.get_client()
        response = await client._get("/api/users")  # noqa: SLF001
        users = response_cls.from_json(response).users
        return len(users)

    async def count_recent_sessions(self) -> int:
        """Fetch and count open sessions with recent update time from API."""
        client = await self.get_client()
        response = await client._get("api/sessions/open")  # noqa: SLF001
        sessions = OpenSessionsResponse.from_json(response).filter_active_sessions()
        return len(sessions)

    async def count_open_sessions(self) -> int:
        """Fetch and count open sessions from API."""
        client = await self.get_client()
        response = await client._get("api/sessions/open")  # noqa: SLF001
        sessions = OpenSessionsResponse.from_json(response).sessions
        return len(sessions)

    async def count_users_online(self) -> int:
        """Fetch and count users online from API."""
        client = await self.get_client()
        response = await client._get("api/users/online")  # noqa: SLF001
        users_online = UsersOnlineResponse.from_json(response).users_online
        return len(users_online)

    async def library_stats(self) -> dict[str, LibraryStats]:
        """Fetch library stats from API."""
        libraries = await self.get_libraries()
        client = await self.get_client()
        stats = {}
        for library in libraries:
            response = await client._get(f"api/libraries/{library.id_}/stats")  # noqa: SLF001
            stats[library.id_] = LibraryStats.from_json(response)
        return stats

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint."""
        data = {}
        try:
            for method in API_DATA_METHODS:
                _LOGGER.debug("Fetched %s", method)
                data[method] = await getattr(self, method)()
                _LOGGER.debug("Fetched %s", data[method])
            data["count_libraries"] = len(data["library_stats"].keys())
        except ClientError as err:
            msg = "Error fetching data"
            raise UpdateFailed(msg) from err
        else:
            return data
