"""Shared entity plumbing for the Audiobookshelf integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .audiobook_shelf_data_update_coordinator import AudiobookShelfDataUpdateCoordinator
from .const import DOMAIN


def device_info_for(
    entry: ConfigEntry, coordinator: AudiobookShelfDataUpdateCoordinator
) -> DeviceInfo:
    """Describe the server that every entity in this integration belongs to."""
    # Shared rather than repeated per platform: two entities disagreeing on
    # the identifiers would register two devices for the one server.
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        entry_type=DeviceEntryType.SERVICE,
        name="Audiobookshelf",
        manufacturer="advplyr",
        sw_version=coordinator.server_version,
        configuration_url=coordinator.api_url,
    )
