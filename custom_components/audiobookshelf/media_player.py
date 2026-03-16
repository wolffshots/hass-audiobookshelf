"""Module containing the media player platform for the Audiobookshelf integration."""

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

SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.SEEK
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the media player platform."""
    coordinator: AudiobookShelfDataUpdateCoordinator = hass.data[DOMAIN]
    tracked: set[str] = set()

    def _add_new_players() -> None:
        sessions = coordinator.data.get("active_sessions", []) if coordinator.data else []
        new_entities = []
        for session in sessions:
            session_id = session.get("id")
            if session_id and session_id not in tracked:
                tracked.add(session_id)
                new_entities.append(AudiobookShelfMediaPlayer(coordinator, session_id))
        if new_entities:
            async_add_entities(new_entities)

    _add_new_players()
    coordinator.async_add_listener(_add_new_players)


class AudiobookShelfMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representation of an active Audiobookshelf playback session."""

    coordinator: AudiobookShelfDataUpdateCoordinator
    _attr_supported_features = SUPPORTED_FEATURES
    _attr_media_content_type = MediaType.MUSIC

    def __init__(
        self,
        coordinator: AudiobookShelfDataUpdateCoordinator,
        session_id: str,
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator, None)
        self._session_id = session_id

    def _get_session(self) -> dict[str, Any] | None:
        """Return the current session dict for this player."""
        if not self.coordinator.data:
            return None
        for session in self.coordinator.data.get("active_sessions", []):
            if session.get("id") == self._session_id:
                return session
        return None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.coordinator.api_url}_mediaplayer_{self._session_id}"

    @property
    def name(self) -> str:
        """Return the name of this player."""
        session = self._get_session()
        if session:
            username = session.get("username") or session.get("user_id") or self._session_id
            return f"Audiobookshelf {username}"
        return f"Audiobookshelf {self._session_id}"

    @property
    def state(self) -> MediaPlayerState:
        """Return the playback state."""
        if self._get_session() is None:
            return MediaPlayerState.IDLE
        return MediaPlayerState.PLAYING

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
        """Return the duration of current media in seconds."""
        session = self._get_session()
        return session.get("duration") if session else None

    @property
    def media_position(self) -> float | None:
        """Return the current playback position in seconds."""
        session = self._get_session()
        return session.get("current_time") if session else None

    @property
    def media_image_url(self) -> str | None:
        """Return the cover art URL."""
        session = self._get_session()
        if not session:
            return None
        cover_path = session.get("cover_path")
        if cover_path:
            return f"{self.coordinator.api_url}{cover_path}"
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
            "play_method": session.get("play_method"),
            "media_type": session.get("media_type"),
            "updated_at": session.get("updated_at"),
        }

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
