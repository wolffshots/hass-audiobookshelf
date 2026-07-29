"""Module containing the services platform for the Audiobookshelf integration."""

from logging import getLogger
from typing import cast

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aioaudiobookshelf.exceptions import AbsError
from aioaudiobookshelf.schema.library import LibraryItemMinifiedBook
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .audiobook_shelf_data_update_coordinator import AudiobookShelfDataUpdateCoordinator
from .const import DOMAIN

SERVICE_REMOVE_PROGRESS = "remove_my_progress"

SERVICE_ATTRIBUTE_SERIES_NAME = "series_name"

SUPPORTED_SERVICES = (SERVICE_REMOVE_PROGRESS,)

# The match is a substring test against every item in every library, and the
# deletion cannot be undone, so an empty or blank name must never reach the
# handler - it would match every book on the server.
SERVICE_SCHEMAS = {
    SERVICE_REMOVE_PROGRESS: vol.Schema(
        {
            vol.Required(SERVICE_ATTRIBUTE_SERIES_NAME): vol.All(
                cv.string, vol.Strip, vol.Length(min=1)
            ),
        }
    ),
}

_LOGGER = getLogger(__name__)


def async_setup_services(hass: HomeAssistant) -> bool:
    """Set up the Audiobookshelf services."""

    def loaded_coordinator() -> AudiobookShelfDataUpdateCoordinator:
        """Return the coordinator, or explain why the action cannot run."""
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            msg = "Audiobookshelf is not configured"
            raise ServiceValidationError(msg)
        if entries[0].state is not ConfigEntryState.LOADED:
            msg = "The Audiobookshelf configuration entry is not loaded"
            raise ServiceValidationError(msg)
        return cast("AudiobookShelfDataUpdateCoordinator", entries[0].runtime_data)

    async def async_handle_remove_progress(call: ServiceCall) -> None:
        """Handle the remove progress service call."""
        coordinator = loaded_coordinator()
        series_name: str = call.data[SERVICE_ATTRIBUTE_SERIES_NAME].casefold()
        removed = 0

        _LOGGER.debug("Searching for %s", series_name)
        try:
            client = await coordinator.get_client()
            for library in await client.get_all_libraries():
                async for response in client.get_library_items(library_id=library.id_):
                    if not response.results:
                        break
                    for item in response.results:
                        if not isinstance(item, LibraryItemMinifiedBook):
                            continue
                        item_series_name = item.media.metadata.series_name
                        if (
                            not isinstance(item_series_name, str)
                            or series_name not in item_series_name.casefold()
                        ):
                            continue
                        progress = await client.get_my_media_progress(item_id=item.id_)
                        if progress is None:
                            continue
                        _LOGGER.debug(
                            "Removing progress for %s",
                            item.media.metadata.title_ignore_prefix,
                        )
                        await client.remove_my_media_progress(
                            media_progress_id=progress.id_
                        )
                        removed += 1
        except AbsError as err:
            # Deletions already made cannot be rolled back, so say how far it
            # got rather than reporting a bare failure.
            msg = f"Removing progress failed after {removed} item(s): {err}"
            raise HomeAssistantError(msg) from err
        finally:
            _LOGGER.debug("Removed progress for %s item(s)", removed)
            await coordinator.async_request_refresh()

    services = {
        SERVICE_REMOVE_PROGRESS: async_handle_remove_progress,
    }
    for service in SUPPORTED_SERVICES:
        hass.services.async_register(
            DOMAIN, service, services[service], schema=SERVICE_SCHEMAS[service]
        )

    return True
