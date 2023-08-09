"""Init for audiobookshelf integration"""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any, Literal

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from requests import HTTPError, Timeout

from custom_components.audiobookshelf.api import AudiobookshelfApiClient

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_HOST,
    DOMAIN,
    ISSUE_URL,
    SCAN_INTERVAL,
    VERSION,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)


class AudiobookshelfDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AudiobookshelfApiClient,
    ) -> None:
        """Initialize."""
        self.api = client
        self.platforms = []

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self) -> Coroutine[Any, Any, dict[str, None]]:
        """Update data via library."""
        update = {"connectivity": None, "users": None, "sessions": None}
        try:
            connectivity_update = await self.api.api_wrapper(
                method="get",
                url=self.api.get_host() + "/ping",
            )
            _LOGGER.debug(
                """async_update connectivity_update: %s""",
                connectivity_update,
            )
            update["connectivity"] = connectivity_update
        except ConnectionError:
            update["connectivity"] = "ConnectionError: Unable to connect."
        except Timeout:
            update["connectivity"] = "TimeoutError: Request timed out."
        except HTTPError as http_error:
            update["connectivity"] = f"HTTPError: {http_error}"
        except Exception as exception:
            _LOGGER.error("Unhandled error occurred: %s", exception)
            raise  # Re-raise the exception to allow it to be properly handled elsewhere
        try:
            users_update = await self.api.api_wrapper(
                method="get",
                url=self.api.get_host() + "/api/users",
            )
            num_users = self.api.count_active_users(users_update)
            _LOGGER.debug("""async_update num_users: %s""", num_users)
            update["users"] = num_users
        except ConnectionError:
            update["users"] = "ConnectionError: Unable to connect."
        except Timeout:
            update["users"] = "TimeoutError: Request timed out."
        except HTTPError as http_error:
            update["users"] = f"HTTPError: {http_error}"
        except Exception as exception:
            _LOGGER.error("Unhandled error occurred: %s", exception)
            raise  # Re-raise the exception to allow it to be properly handled elsewhere
        try:
            online_users_update = await self.api.api_wrapper(
                method="get",
                url=self.api.get_host() + "/api/users/online",
            )
            open_sessions = self.api.count_open_sessions(online_users_update)
            _LOGGER.debug("""async_update open_sessions: %s""", open_sessions)
            update["sessions"] = open_sessions
        except ConnectionError:
            update["sessions"] = "ConnectionError: Unable to connect."
        except Timeout:
            update["sessions"] = "TimeoutError: Request timed out."
        except HTTPError as http_error:
            update["sessions"] = f"HTTPError: {http_error}"
        except Exception as exception:
            _LOGGER.error("Unhandled error occurred: %s", exception)
            raise  # Re-raise the exception to allow it to be properly handled elsewhere
        return update


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> Coroutine[Any, Any, Literal[True]]:
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
        _LOGGER.info(
            """
            -------------------------------------------------------------------
            Audiobookshelf
            Version: %s
            This is a custom integration!
            If you have any issues with this you need to open an issue here:
            %s
            -------------------------------------------------------------------
            """,
            VERSION,
            ISSUE_URL,
        )

    host = entry.data.get(CONF_HOST)
    access_token = entry.data.get(CONF_ACCESS_TOKEN)

    session = async_get_clientsession(hass)
    client = AudiobookshelfApiClient(host, access_token, session)

    coordinator = AudiobookshelfDataUpdateCoordinator(hass, client=client)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in ["binary_sensor", "sensor"]:
        if entry.options.get(platform, True):
            coordinator.platforms.append(platform)
            hass.async_add_job(
                hass.config_entries.async_forward_entry_setup(entry, platform),
            )
    entry.add_update_listener(async_reload_entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in ["binary_sensor", "sensor"]
                if platform in coordinator.platforms
            ],
        ),
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
