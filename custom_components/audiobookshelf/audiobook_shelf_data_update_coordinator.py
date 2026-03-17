"""Module containing the data update coordinator the Audiobookshelf integration."""

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

# Fast-poll interval for the dedicated media player coordinator (seconds).
MEDIA_PLAYER_POLL_INTERVAL = 10


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


class MediaPlayerSessionCoordinator(DataUpdateCoordinator):
    """Lightweight coordinator that only polls /api/sessions/open on a fast interval.

    Used exclusively by the media player platform to enable accurate
    play/pause detection without burdening the main coordinator with
    high-frequency requests to all endpoints.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        api_url: str,
        token: str,
        poll_interval: int = MEDIA_PLAYER_POLL_INTERVAL,
    ) -> None:
        """Initialize."""
        self.api_url = api_url
        self.token = token
        super().__init__(
            hass,
            _LOGGER,
            name="audiobookshelf_media_player",
            update_interval=timedelta(seconds=poll_interval),
        )

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch /api/sessions/open and enrich sessions with usernames."""
        http_session = async_get_clientsession(self.hass)
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with http_session.get(
                f"{self.api_url.rstrip('/')}/api/sessions/open",
                headers=headers,
            ) as resp:
                sessions_data = await resp.json(content_type=None)

            async with http_session.get(
                f"{self.api_url.rstrip('/')}/api/users",
                headers=headers,
            ) as resp:
                users_data = await resp.json(content_type=None)
        except ClientError as err:
            raise UpdateFailed(f"Error fetching session data: {err}") from err

        users_by_id: dict[str, str] = {
            str(u.get("id", "")): str(u.get("username", ""))
            for u in users_data.get("users", [])
        }

        result = []
        for session in sessions_data.get("sessions", []):
            user_id = str(session.get("userId", ""))
            result.append(
                {
                    "id": session.get("id"),
                    "user_id": user_id,
                    "username": users_by_id.get(user_id),
                    "display_title": session.get("displayTitle"),
                    "display_author": session.get("displayAuthor"),
                    "current_time": session.get("currentTime"),
                    "duration": session.get("duration"),
                    "play_method": session.get("playMethod"),
                    "media_type": session.get("mediaType"),
                    "cover_path": session.get("coverPath"),
                    "library_item_id": session.get("libraryItemId"),
                    "updated_at": session.get("updatedAt"),
                }
            )
        return result


class AudiobookShelfDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Audiobookshelf data from the API."""

    _client: AdminClient = None  # type: ignore[import-untyped]
    api_url: str = ""
    token: str = ""

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
        client = await self.get_client()
        response = await client._get("/api/users")  # noqa: SLF001
        users = AllUsersResponse.from_json(response).users
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
                    "library_item_id": getattr(session, "library_item_id", None),
                    "updated_at": getattr(session, "updated_at", None),
                }
            )
        return result

    async def user_progress(self) -> list[UserProgress]:
        """Fetch per-user reading progress."""
        http_session = async_get_clientsession(self.hass)
        headers = {"Authorization": f"Bearer {self.token}"}

        url = f"{self.api_url.rstrip('/')}/api/users"
        async with http_session.get(url, headers=headers) as resp:
            data = await resp.json(content_type=None)
        users = data.get("users", [])

        active_sessions_url = f"{self.api_url.rstrip('/')}/api/sessions/open"
        async with http_session.get(active_sessions_url, headers=headers) as resp:
            sessions_data = await resp.json(content_type=None)

        current_time_ms = int(time.time() * 1000)
        active_by_user: dict[str, dict] = {}
        for session in sessions_data.get("sessions", []):
            updated_at = session.get("updatedAt") or 0
            if (current_time_ms - updated_at) < (120 * 1000):
                user_id = session.get("userId", "")
                active_by_user[str(user_id)] = session

        progress_list = []
        for user in users:
            user_id = str(user.get("id", ""))
            username = str(user.get("username", "unknown"))

            active = active_by_user.get(user_id)
            if active:
                current_time = active.get("currentTime")
                duration = active.get("duration")
                progress = (
                    float(current_time) / float(duration)
                    if current_time and duration and float(duration) > 0
                    else 0.0
                )
                progress_list.append(
                    UserProgress(
                        user_id=user_id,
                        username=username,
                        item_id=str(active.get("libraryItemId")),
                        title=active.get("displayTitle"),
                        author=active.get("displayAuthor"),
                        progress=round(progress, 4),
                        current_time=float(current_time) if current_time else None,
                        duration=float(duration) if duration else None,
                        is_finished=False,
                        cover_path=active.get("coverPath"),
                    )
                )
                continue

            media_progress = user.get("mediaProgress") or []
            active_progress = sorted(
                [
                    p for p in media_progress
                    if not p.get("isFinished", False)
                    and p.get("progress", 0) > 0
                ],
                key=lambda p: p.get("lastUpdate") or p.get("updatedAt") or 0,
                reverse=True,
            )
            current = active_progress[0] if active_progress else None
            progress_list.append(
                UserProgress(
                    user_id=user_id,
                    username=username,
                    item_id=str(current.get("libraryItemId")) if current else None,
                    title=None,
                    author=None,
                    progress=float(current.get("progress", 0)) if current else None,
                    current_time=float(current.get("currentTime", 0)) if current else None,
                    duration=float(current.get("duration", 0)) if current else None,
                    is_finished=bool(current.get("isFinished", False)) if current else False,
                    cover_path=None,
                )
            )
        return progress_list

    async def recently_added(self) -> list[dict[str, Any]]:
        """Fetch recently added items across all libraries."""
        libraries = await self.get_libraries()
        http_session = async_get_clientsession(self.hass)
        headers = {"Authorization": f"Bearer {self.token}"}
        items = []
        for library in libraries:
            try:
                url = (
                    f"{self.api_url.rstrip('/')}/api/libraries/{library.id_}/items"
                    f"?sort=addedAt&desc=1&limit=5"
                )
                async with http_session.get(url, headers=headers) as resp:
                    data = await resp.json(content_type=None)
                for item in data.get("results", []):
                    media = item.get("media", {})
                    metadata = media.get("metadata", {})
                    items.append(
                        {
                            "library": library.name,
                            "library_id": library.id_,
                            "item_id": item.get("id"),
                            "title": metadata.get("title"),
                            "author": metadata.get("authorName") or metadata.get("author"),
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
                _LOGGER.debug("Fetching %s", method)
                data[method] = await getattr(self, method)()
                _LOGGER.debug("Fetched %s: %s", method, data[method])
            data["count_libraries"] = len(data["library_stats"].keys())
        except ClientError as err:
            msg = "Error fetching data"
            raise UpdateFailed(msg) from err
        else:
            return data
