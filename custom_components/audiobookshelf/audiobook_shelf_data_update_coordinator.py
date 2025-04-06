from dataclasses import dataclass
from datetime import timedelta
from logging import getLogger
from typing import Annotated

from aioaudiobookshelf import SessionConfiguration, get_admin_client_by_token, AdminClient
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
    "count_open_sessions",
    "library_stats",
]


@dataclass(kw_only=True)
class AllUsersResponse(_BaseModel):
    """AllUsersResponse."""
    users: list[_UserBase]


@dataclass(kw_only=True)
class UsersOnlineResponse(_BaseModel):
    """AllUsersResponse."""
    users_online: Annotated[list[_UserBase], Alias("usersOnline")]
    open_sessions: Annotated[list[PlaybackSession], Alias("openSessions")]


@dataclass(kw_only=True)
class LibraryStats(_BaseModel):
    """LibraryStats."""
    total_authors: Annotated[int, Alias("totalAuthors")]
    total_genres: Annotated[int, Alias("totalGenres")]
    total_items: Annotated[int, Alias("totalItems")]
    total_size: Annotated[int, Alias("totalSize")]
    total_duration: Annotated[float, Alias("totalDuration")]
    total_audio_tracks: Annotated[int, Alias("numAudioTracks")]


class AudiobookShelfDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Audiobookshelf data from the API."""
    _client: AdminClient = None

    def __init__(self, hass: HomeAssistant, scan_interval: int, api_url: str, token: str) -> None:
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
        return await (await self.get_client()).get_all_libraries()

    async def count_users(self) -> int:
        """Fetch count active users from API."""
        response_cls: type[AllUsersResponse] = AllUsersResponse
        client = await self.get_client()
        response = await client._get("/api/users")
        users = response_cls.from_json(response).users
        return len(users)

    async def count_open_sessions(self) -> int:
        """Fetch count open sessions from API."""
        client = await self.get_client()
        response = await client._get("api/users/online")
        open_sessions = UsersOnlineResponse.from_json(response).open_sessions
        return len(open_sessions)

    async def library_stats(self) -> dict[str, LibraryStats]:
        """Fetch library stats from API."""
        libraries = await self.get_libraries()
        client = await self.get_client()
        stats = {}
        for library in libraries:
            response = await client._get(f"api/libraries/{library.id_}/stats")
            stats[library.id_] = LibraryStats.from_json(response)
        return stats

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint."""
        data = {}
        try:
            for method in API_DATA_METHODS:
                _LOGGER.debug(f"Fetching {method}")
                data[method] = await getattr(self, method)()
                _LOGGER.debug(f"Fetched {data[method]}")
            data["count_libraries"] = len(data["library_stats"].keys())
            return data
        except ClientError as err:
            msg = "Error fetching data"
            raise UpdateFailed(msg) from err

