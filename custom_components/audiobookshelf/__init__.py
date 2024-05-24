"""Custom component for Audiobookshelf."""
import logging
from homeassistant.helpers import discovery
# from .sensor import async_refresh_libraries

DOMAIN = "audiobookshelf"

_LOGGER = logging.getLogger(__name__)

# async def async_setup(hass, config):
#     """Set up the Audiobookshelf component."""
#     # Schedule the setup of sensor platform
#     hass.async_create_task(discovery.async_load_platform(hass, "sensor", DOMAIN, {}, config))
#     hass.async_create_task(async_refresh_libraries(hass))

#     return True

async def async_setup(hass, config):
    """Set up the Audiobookshelf component."""
    # Schedule the setup of sensor platform
    hass.async_create_task(discovery.async_load_platform(hass, "sensor", DOMAIN, {}, config))

    # Use a helper to get the async_add_entities function from the sensor platform setup
    # async def platform_setup():
    #     """Wait for platform to be set up and then start refreshing libraries."""
    #     platform = hass.data.get('sensor_platform')
    #     if platform:
    #         await async_refresh_libraries(hass, platform.async_add_entities)

    # hass.async_create_task(platform_setup())

    return True