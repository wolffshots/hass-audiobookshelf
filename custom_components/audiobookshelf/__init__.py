"""Custom component for Audiobookshelf."""

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_URL): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=300): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


def clean_config(data: dict) -> dict:
    """Remove the api key from config."""
    if bool(data[CONF_API_KEY]):
        data[CONF_API_KEY] = "<redacted>"
    return data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Audiobookshelf from a config entry."""
    if entry.data is None:
        error_message = "Configuration not found"
        raise ConfigEntryNotReady(error_message)

    _LOGGER.debug(
        "Setting up Audiobookshelf with config: %s", clean_config(entry.data.copy())
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
