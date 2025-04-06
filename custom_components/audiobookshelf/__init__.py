"""Custom component for Audiobookshelf."""

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from custom_components.audiobookshelf.config_flow import validate_config, verify_config
from .audiobook_shelf_data_update_coordinator import AudiobookShelfDataUpdateCoordinator

from .const import DOMAIN, PLATFORMS, VERSION
from .services import async_setup_services

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_URL): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=300): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


def clean_config(data: dict[str, str]) -> dict[str, str]:
    """Remove the api key from config."""
    try:
        if CONF_API_KEY in data:
            data[CONF_API_KEY] = "<redacted>"
    except Exception as e:
        _LOGGER.exception("Failed to clean config, most likely not valid", exc_info=e)
    return data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Audiobookshelf from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    if entry.data is None:
        error_message = "Configuration not found"
        raise ConfigEntryNotReady(error_message)

    _LOGGER.debug(
        "Setting up Audiobookshelf with config: %s", clean_config(entry.data.copy())
    )

    errors = validate_config(entry.data.copy())
    errors.update(await verify_config(entry.data.copy()))
    if len(errors.keys()) > 0:
        _LOGGER.debug("Config validation errors: %s", errors)
        raise ConfigEntryNotReady(errors)

    scan_interval = int(entry.data[CONF_SCAN_INTERVAL])
    api_url = entry.data[CONF_URL]
    token = entry.data[CONF_API_KEY]
    coordinator = AudiobookShelfDataUpdateCoordinator(
        hass,
        scan_interval=scan_interval,
        api_url=api_url,
        token=token,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN] = coordinator

    async_setup_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
