"""Update platform reporting whether a newer Audiobookshelf server exists."""

from datetime import timedelta
from logging import getLogger

from aioaudiobookshelf.exceptions import AbsError
from aiohttp import ClientError
from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.audiobookshelf import AudiobookshelfConfigEntry
from custom_components.audiobookshelf.audiobook_shelf_data_update_coordinator import (
    AudiobookShelfDataUpdateCoordinator,
)
from custom_components.audiobookshelf.const import (
    GITHUB_LATEST_RELEASE_URL,
    REQUEST_TIMEOUT,
    check_for_updates_for,
)
from custom_components.audiobookshelf.entity import device_info_for

_LOGGER = getLogger(__name__)

# GitHub allows 60 unauthenticated requests an hour per address and releases
# appear a few times a month, so hourly is generous either way. This is
# deliberately separate from the sensor poll: the release check is the one
# thing here that leaves the local network, and it must not be able to hold
# up or fail a poll of the user's own server.
SCAN_INTERVAL = timedelta(hours=1)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AudiobookshelfConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the update platform, when the user has opted in."""
    if not check_for_updates_for(entry):
        # The platform is forwarded either way so that unloading always
        # matches what was set up. Opting out simply creates no entity.
        _LOGGER.debug("Update checking is disabled, not adding an update entity")
        return

    async_add_entities([AudiobookshelfUpdate(entry.runtime_data, entry)], True)  # noqa: FBT003


class AudiobookshelfUpdate(UpdateEntity):
    """Compares the running server against the newest published release."""

    _attr_has_entity_name = True
    _attr_translation_key = "server"
    _attr_device_class = UpdateDeviceClass.FIRMWARE

    def __init__(
        self,
        coordinator: AudiobookShelfDataUpdateCoordinator,
        entry: AudiobookshelfConfigEntry,
    ) -> None:
        """Initialize the update entity."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_server_update"
        self._attr_device_info = device_info_for(entry, coordinator)

    @property
    def installed_version(self) -> str | None:
        """Return the version the server is running."""
        return self.coordinator.server_version

    @property
    def release_url(self) -> str | None:
        """Link to the release notes for the newest version."""
        if self.latest_version is None:
            return None
        return (
            "https://github.com/advplyr/audiobookshelf/releases/tag/"
            f"v{self.latest_version}"
        )

    async def async_update(self) -> None:
        """Refresh both halves of the comparison."""
        # The installed version is cached on the coordinator and otherwise only
        # re-read when the client is rebuilt, so without this the entity would
        # go on offering an update the user had already applied.
        try:
            await self.coordinator.async_refresh_server_version()
        except AbsError as err:
            _LOGGER.debug("Could not re-read the server version: %s", err)

        latest = await self._async_latest_release()
        if latest is not None:
            # Keep the last good answer rather than dropping to unknown, so a
            # momentary GitHub failure does not blank the entity.
            self._attr_latest_version = latest

    async def _async_latest_release(self) -> str | None:
        """Ask GitHub for the newest release, or None if it cannot be reached."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                GITHUB_LATEST_RELEASE_URL,
                headers={"Accept": "application/vnd.github+json"},
                timeout=REQUEST_TIMEOUT,
            ) as response:
                response.raise_for_status()
                body = await response.json()
        except (ClientError, TimeoutError) as err:
            _LOGGER.warning("Could not reach GitHub to check for updates: %s", err)
            return None
        except (ValueError, LookupError) as err:
            _LOGGER.warning("Unexpected response from the GitHub API: %s", err)
            return None

        tag = body.get("tag_name") if isinstance(body, dict) else None
        if not isinstance(tag, str) or not tag:
            _LOGGER.warning("GitHub release response carried no usable tag_name")
            return None

        # Releases are tagged v2.36.0 while the server reports 2.36.0.
        return tag.removeprefix("v")
