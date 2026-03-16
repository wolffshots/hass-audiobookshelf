"""Module containing the data update coordinator the Audiobookshelf integration."""

import json
import time
from dataclasses import dataclass
from datetime import timedelta
from logging import getLogger
from typing import Annotated, Any

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
    "active_sessions",
    "user_progress",
    "library_stats",
    "recently_added",
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


@dataclass
class UserProgress:
    """Represents a single user's current reading/listening progress."""

    user_id: str
    username: str
    item_id: str | None
    title: str | None
    author: str | None
    progress: float | None
    current_time: float | None
    duration: float | None
    is_finished: bool
    cover_path: str | None


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
        response = await client._get("/api/sessions/open")  # noqa: SLF001
        sessions = OpenSessionsResponse.from_json(response).filter_active_sessions()
        return len(sessions)

    async def count_open_sessions(self) -> int:
        """Fetch and count open sessions from API."""
        client = await self.get_client()
        response = await client._get("/api/sessions/open")  # noqa: SLF001
        sessions = OpenSessionsResponse.from_json(response).sessions
        return len(sessions)

    async def count_users_online(self) -> int:
        """Fetch and count users online from API."""
        client = await self.get_client()
        response = await client._get("/api/users/online")  # noqa: SLF001
        users_online = UsersOnlineResponse.from_json(response).users_online
        return len(users_online)

    async def active_sessions(self) -> list[dict[str, Any]]:
        """Fetch full active session objects for media player use."""
        client = await self.get_client()
        response = await client._get("/api/sessions/open")  # noqa: SLF001
        sessions = OpenSessionsResponse.from_json(response).filter_active_sessions()
        users_response = await client._get("/api/users")  # noqa: SLF001
        users = {
            str(getattr(u, "id_", "") or getattr(u, "id", "")): u
            for u in AllUsersResponse.from_json(users_response).users
        }
        result = []
        for session in sessions:
            user_id = str(getattr(session, "user_id", "") or "")
            user = users.get(user_id)
            username = getattr(user, "username", None) if user is not None else None
            result.append(
                {
                    "id": getattr(session, "id_", None) or getattr(session, "id", None),
                    "user_id": user_id,
                    "username": username,
                    "display_title": getattr(session, "display_title", None),
                    "display_author": getattr(session, "display_author", None),
                    "current_time": getattr(session, "current_time", None),
                    "duration": getattr(session, "duration", None),
                    "play_method": getattr(session, "play_method", None),
                    "media_type": getattr(session, "media_type", None),
                    "cover_path": getattr(session, "cover_path", None),
                    "updated_at": getattr(session, "updated_at", None),
                }
            )
        return result

    async def user_progress(self) -> list[UserProgress]:
        """Fetch per-user reading progress from API."""
        client = await self.get_client()
        response = await client._get("/api/users")  # noqa: SLF001
        users = AllUsersResponse.from_json(response).users
        progress_list = []
        for user in users:
            media_progress = getattr(user, "media_progress", []) or []
            active = sorted(
                [
                    p
                    for p in media_progress
                    if not getattr(p, "is_finished", False)
                    and getattr(p, "progress", 0) > 0
                ],
                key=lambda p: getattr(p, "last_update", 0) or 0,
                reverse=True,
            )
            current = active[0] if active else None
            progress_list.append(
                UserProgress(
                    user_id=str(getattr(user, "id_", "") or getattr(user, "id", "")),
                    username=str(getattr(user, "username", "unknown")),
                    item_id=str(getattr(current, "library_item_id", None))
                    if current
                    else None,
                    title=None,
                    author=None,
                    progress=float(getattr(current, "progress", 0)) if current else None,
                    current_time=float(getattr(current, "current_time", 0))
                    if current
                    else None,
                    duration=float(getattr(current, "duration", 0)) if current else None,
                    is_finished=bool(getattr(current, "is_finished", False))
                    if current
                    else False,
                    cover_path=None,
                )
            )
        return progress_list

    async def recently_added(self) -> list[dict[str, Any]]:
        """Fetch recently added items across all libraries."""
        libraries = await self.get_libraries()
        client = await self.get_client()
        items = []
        for library in libraries:
            try:
                response = await client._get(  # noqa: SLF001
                    f"/api/libraries/{library.id_}/recentlyadded?limit=5"
                )
                data = json.loads(response)
                for item in data.get("libraryItems", []):
                    media = item.get("media", {})
                    metadata = media.get("metadata", {})
                    items.append(
                        {
                            "library": library.name,
                            "library_id": library.id_,
                            "item_id": item.get("id"),
                            "title": metadata.get("title"),
                            "author": metadata.get("authorName")
                            or metadata.get("author"),
                            "added_at": item.get("addedAt"),
                        }
                    )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Could not fetch recently added for %s: %s", library.name, err
                )
        items.sort(key=lambda x: x.get("added_at") or 0, reverse=True)
        return items[:10]

    async def library_stats(self) -> dict[str, LibraryStats]:
        """Fetch library stats from API."""
        libraries = await self.get_libraries()
        client = await self.get_client()
        stats = {}
        for library in libraries:
            response = await client._get(  # noqa: SLF001
                f"/api/libraries/{library.id_}/stats"
            )
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
