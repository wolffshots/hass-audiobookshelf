from logging import getLogger
from typing import cast

from aioaudiobookshelf.schema.library import LibraryItemMinifiedPodcast, LibraryItemMinifiedBook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import device_registry

from . import AudiobookShelfDataUpdateCoordinator
from .const import DOMAIN

SERVICE_REMOVE_PROGRESS = "remove_my_progress"

SERVICE_ATTRIBUTE_SERIES_NAME = "series_name"

SUPPORTED_SERVICES = (
    SERVICE_REMOVE_PROGRESS,
)

_LOGGER = getLogger(__name__)

def async_setup_services(hass: HomeAssistant):
    async def async_handle_remove_progress(call: ServiceCall):
        coordinator: AudiobookShelfDataUpdateCoordinator = hass.data[DOMAIN]
        series_name = call.data.get(SERVICE_ATTRIBUTE_SERIES_NAME)

        client = await coordinator.get_client()
        libraries = await client.get_all_libraries()
        _LOGGER.debug(f"Searching for {series_name}")
        for library in libraries:
            async for response in client.get_library_items(library_id=library.id_):
                if not response.results:
                    break
                for lib_item_minified in response.results:
                    if isinstance(lib_item_minified, LibraryItemMinifiedPodcast):
                        pass
                    if isinstance(lib_item_minified, LibraryItemMinifiedBook):
                        if series_name in lib_item_minified.media.metadata.series_name or series_name == lib_item_minified.media.metadata.series_name:
                            media_progress = await client.get_my_media_progress(item_id=lib_item_minified.id_)
                            _LOGGER.debug(f"found match of {lib_item_minified.media.metadata.title_ignore_prefix}")
                            if media_progress is not None:
                                _LOGGER.debug(f"deleting media progress for {lib_item_minified.media.metadata.title_ignore_prefix}")
                                await client.remove_my_media_progress(media_progress_id=media_progress.id_)
                        else:
                            _LOGGER.debug(f"not found match of {lib_item_minified.media.metadata.title_ignore_prefix}")


        await coordinator.async_request_refresh()

    services = {
        SERVICE_REMOVE_PROGRESS: async_handle_remove_progress,
    }
    for service in SUPPORTED_SERVICES:
        hass.services.async_register(DOMAIN, service, services[service])

    return True

@callback
def async_unload_services(hass) -> None:
    for service in SUPPORTED_SERVICES:
        hass.services.async_remove(DOMAIN, service)
