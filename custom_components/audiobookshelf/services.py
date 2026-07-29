"""Module containing the services platform for the Audiobookshelf integration."""

from logging import getLogger
from typing import TYPE_CHECKING

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aioaudiobookshelf.schema.library import (
    LibraryItemMinifiedBook,
    LibraryItemMinifiedPodcast,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback

from .const import DOMAIN

if TYPE_CHECKING:
    from . import AudiobookShelfDataUpdateCoordinator

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

    async def async_handle_remove_progress(call: ServiceCall) -> None:
        """Handle the remove progress service call."""
        coordinator: AudiobookShelfDataUpdateCoordinator = hass.data[DOMAIN]
        series_name: str = call.data[SERVICE_ATTRIBUTE_SERIES_NAME].casefold()

        client = await coordinator.get_client()
        libraries = await client.get_all_libraries()
        _LOGGER.debug("Searching for %s", series_name)
        for library in libraries:
            async for response in client.get_library_items(library_id=library.id_):
                if not response.results:
                    break
                for lib_item_minified in response.results:
                    if isinstance(lib_item_minified, LibraryItemMinifiedPodcast):
                        pass
                    if isinstance(lib_item_minified, LibraryItemMinifiedBook):
                        item_series_name = lib_item_minified.media.metadata.series_name
                        if (
                            isinstance(item_series_name, str)
                            and series_name in item_series_name.casefold()
                        ):
                            media_progress = await client.get_my_media_progress(
                                item_id=lib_item_minified.id_
                            )
                            _LOGGER.debug(
                                "found match of %s",
                                lib_item_minified.media.metadata.title_ignore_prefix,
                            )
                            if media_progress is not None:
                                _LOGGER.debug(
                                    "deleting media progress for %s",
                                    lib_item_minified.media.metadata.title_ignore_prefix,
                                )
                                await client.remove_my_media_progress(
                                    media_progress_id=media_progress.id_
                                )
                        else:
                            _LOGGER.debug(
                                "not found match of %s",
                                lib_item_minified.media.metadata.title_ignore_prefix,
                            )

        await coordinator.async_request_refresh()

    services = {
        SERVICE_REMOVE_PROGRESS: async_handle_remove_progress,
    }
    for service in SUPPORTED_SERVICES:
        hass.services.async_register(
            DOMAIN, service, services[service], schema=SERVICE_SCHEMAS[service]
        )

    return True


@callback
def async_unload_services(hass: HomeAssistant) -> None:
    """Unload the Audiobookshelf services from hass."""
    for service in SUPPORTED_SERVICES:
        hass.services.async_remove(DOMAIN, service)
