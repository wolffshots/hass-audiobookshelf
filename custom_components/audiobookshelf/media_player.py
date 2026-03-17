"""Module containing the media player platform for the Audiobookshelf integration."""

from datetime import datetime, timezone
from logging import getLogger
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.audiobookshelf.audiobook_shelf_data_update_coordinator import (
    AudiobookShelfDataUpdateCoordinator,
)
from custom_components.audiobookshelf.const import DOMAIN, VERSION

_LOGGER = getLogger(__name__)

# ABS has no server-side pause/play API.
# State is determined by comparing updatedAt between consecutive polls:
# if updatedAt changed since the last poll -> PLAYING, else -> PAUSED.
SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.PLAY_MEDIA
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the media player platform."""
    coordinator: AudiobookShelfDataUpdateCoordinator = hass.data[DOMAIN]
    tracked: set[str] = set()

    def _sync_players() -> None:
        sessions = coordinator.data.get("active_sessions", []) if coordinator.data else []
        new_entities = []
        for session in sessions:
            user_id = session.get("user_id")
            if user_id and str(user_id) not in tracked:
                tracked.add(str(user_id))
                new_entities.append(AudiobookShelfMediaPlayer(coordinator, str(user_id)))
        if new_entities:
            async_add_entities(new_entities)

    _sync_players()
    coordinator.async_add_listener(_sync_players)


class AudiobookShelfMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a per-user Audiobookshelf playback session."""

    coordinator: AudiobookShelfDataUpdateCoordinator
    _attr_supported_features = SUPPORTED_FEATURES
    _attr_media_content_type = MediaType.MUSIC

    def __init__(
        self,
        coordinator: AudiobookShelfDataUpdateCoordinator,
        user_id: str,
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator, None)
        self._user_id = user_id
        # Tracks the updatedAt value from the previous poll to detect changes.
        self._last_updated_at: int | None = None
        # Cached state so we can hold PAUSED until updatedAt changes again.
        self._cached_state: MediaPlayerState = MediaPlayerState.IDLE

    def _get_session(self) -> dict[str, Any] | None:
        """Return the active session for this user."""
        if not self.coordinator.data:
            return None
        for session in self.coordinator.data.get("active_sessions", []):
            if str(session.get("user_id")) == self._user_id:
                return session
        return None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        Called on every poll. We compare the current updatedAt against the
        previous poll's value to determine if the client is actively playing.
        """
        session = self._get_session()
        if session is None:
            self._cached_state = MediaPlayerState.IDLE
            self._last_updated_at = None
        else:
            current_updated_at = session.get("updated_at")
            if self._last_updated_at is None:
                # First poll for this session — assume playing until proven otherwise.
                self._cached_state = MediaPlayerState.PLAYING
            elif current_updated_at != self._last_updated_at:
                # updatedAt changed since last poll — client is actively syncing.
                self._cached_state = MediaPlayerState.PLAYING
            else:
                # updatedAt identical across two consecutive polls — client is paused.
                self._cached_state = MediaPlayerState.PAUSED
            self._last_updated_at = current_updated_at
        super()._handle_coordinator_update()

    @property
    def unique_id(self) -> str:
        """Return a unique ID per user."""
        return f"{self.coordinator.api_url}_mediaplayer_user_{self._user_id}"

    @property
    def name(self) -> str:
        """Return the name of this player."""
        session = self._get_session()
        username = (session.get("username") if session else None) or self._user_id
        return f"Audiobookshelf {username}"

    @property
    def state(self) -> MediaPlayerState:
        """Return the cached playback state determined on last coordinator update."""
        return self._cached_state

    @property
    def media_title(self) -> str | None:
        """Return the title of current media."""
        session = self._get_session()
        return session.get("display_title") if session else None

    @property
    def media_artist(self) -> str | None:
        """Return the author of current media."""
        session = self._get_session()
        return session.get("display_author") if session else None

    @property
    def media_duration(self) -> float | None:
        """Return the duration in seconds."""
        session = self._get_session()
        if not session:
            return None
        duration = session.get("duration")
        return float(duration) if duration is not None else None

    @property
    def media_position(self) -> float | None:
        """Return the current playback position in seconds."""
        session = self._get_session()
        if not session:
            return None
        current_time = session.get("current_time")
        return float(current_time) if current_time is not None else None

    @property
    def media_position_updated_at(self) -> datetime | None:
        """Return when the position was last updated as a UTC datetime.

        HA uses this to extrapolate the position forward between polls.
        Returning None when paused prevents HA from extrapolating incorrectly.
        """
        if self._cached_state != MediaPlayerState.PLAYING:
            return None
        session = self._get_session()
        if not session:
            return None
        updated_at_ms = session.get("updated_at")
        if updated_at_ms is None:
            return None
        return datetime.fromtimestamp(updated_at_ms / 1000, tz=timezone.utc)

    @property
    def media_image_url(self) -> str | None:
        """Return the cover art URL via ABS API."""
        session = self._get_session()
        if not session:
            return None
        item_id = session.get("library_item_id")
        if item_id:
            return f"{self.coordinator.api_url.rstrip('/')}/api/items/{item_id}/cover"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra session attributes."""
        session = self._get_session()
        if not session:
            return {}
        return {
            "session_id": session.get("id"),
            "user_id": session.get("user_id"),
            "username": session.get("username"),
            "play_method": str(session.get("play_method")),
            "media_type": session.get("media_type"),
            "updated_at": session.get("updated_at"),
            "current_time_seconds": session.get("current_time"),
            "duration_seconds": session.get("duration"),
        }

    async def async_media_play(self) -> None:
        """No server-side play in ABS — refresh coordinator to re-evaluate state."""
        await self.coordinator.async_request_refresh()

    async def async_media_pause(self) -> None:
        """No server-side pause in ABS — refresh coordinator to re-evaluate state."""
        await self.coordinator.async_request_refresh()

    async def async_media_seek(self, position: float) -> None:
        """Seek is not controllable server-side in ABS."""
        _LOGGER.debug(
            "Seek to %.1fs requested for user %s (not supported server-side)",
            position,
            self._user_id,
        )

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.api_url)},
            "name": "Audiobookshelf",
            "manufacturer": "advplyr",
            "sw_version": VERSION,
            "configuration_url": self.coordinator.api_url,
        }
