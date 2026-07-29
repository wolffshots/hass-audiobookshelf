"""Custom component for Audiobookshelf."""

import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .audiobook_shelf_data_update_coordinator import AudiobookShelfDataUpdateCoordinator
from .const import DOMAIN, PLATFORMS
from .services import async_setup_services

type AudiobookshelfConfigEntry = ConfigEntry[AudiobookShelfDataUpdateCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


def clean_config(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of the config with the API key masked."""
    # Builds a new mapping rather than editing in place: the previous version
    # swallowed any exception and returned the argument untouched, so its
    # failure mode was to log the credential it exists to hide.
    return {
        key: "<redacted>" if key == CONF_API_KEY else value
        for key, value in data.items()
    }


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  # noqa: ARG001
    """Register the Audiobookshelf services."""
    # Registering here rather than per entry keeps the actions resolvable
    # while the entry is unloaded or failed, so automations referencing them
    # still validate instead of failing with an unknown service.
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: AudiobookshelfConfigEntry
) -> bool:
    """Set up Audiobookshelf from a config entry."""
    _LOGGER.debug("Setting up Audiobookshelf with config: %s", clean_config(entry.data))

    coordinator = AudiobookShelfDataUpdateCoordinator(
        hass,
        config_entry=entry,
        scan_interval=int(entry.data[CONF_SCAN_INTERVAL]),
        api_url=entry.data[CONF_URL],
        token=entry.data[CONF_API_KEY],
    )

    # This doubles as the setup-time connection test, raising
    # ConfigEntryNotReady or ConfigEntryAuthFailed as appropriate, so no
    # separate probe over its own session is needed.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AudiobookshelfConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
