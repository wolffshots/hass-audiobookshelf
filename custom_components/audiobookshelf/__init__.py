"""Custom component for Audiobookshelf."""

import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .audiobook_shelf_data_update_coordinator import AudiobookShelfDataUpdateCoordinator
from .const import DOMAIN, PLATFORMS, scan_interval_for
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


@callback
def _migrate_url_identifiers(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Re-key entities and the device from the API URL onto the entry id."""
    # v1 built both from the URL, which the user can edit, so moving the
    # server orphaned every entity and created a second device. Rewriting
    # them here preserves history, dashboards and any area assignment.
    old_prefix = f"{entry.data[CONF_URL]}_"

    entity_registry = er.async_get(hass)
    for registry_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if not registry_entry.unique_id.startswith(old_prefix):
            continue
        suffix = registry_entry.unique_id.removeprefix(old_prefix)
        entity_registry.async_update_entity(
            registry_entry.entity_id,
            new_unique_id=f"{entry.entry_id}_{suffix}",
        )

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.data[CONF_URL])}
    )
    if device is not None:
        device_registry.async_update_device(
            device.id,
            new_identifiers={(DOMAIN, entry.entry_id)},
            # v1 put the integration's own version here, where the device
            # registry expects the server's. Dropping it from DeviceInfo does
            # not clear what is already stored, so an upgraded install would
            # keep showing it indefinitely.
            sw_version=None,
        )


async def async_migrate_entry(
    hass: HomeAssistant, entry: AudiobookshelfConfigEntry
) -> bool:
    """Migrate an old config entry."""
    if entry.version == 1:
        _LOGGER.info("Migrating Audiobookshelf entry from version 1 to 2")
        _migrate_url_identifiers(hass, entry)
        hass.config_entries.async_update_entry(entry, version=2)
    return True


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
        scan_interval=scan_interval_for(entry),
        api_url=entry.data[CONF_URL],
        token=entry.data[CONF_API_KEY],
    )

    # This doubles as the setup-time connection test, raising
    # ConfigEntryNotReady or ConfigEntryAuthFailed as appropriate, so no
    # separate probe over its own session is needed.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # The options flow only writes the entry; without this a changed scan
    # interval would not take effect until Home Assistant restarted.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(
    hass: HomeAssistant, entry: AudiobookshelfConfigEntry
) -> None:
    """Reload the entry when its configuration changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: AudiobookshelfConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
