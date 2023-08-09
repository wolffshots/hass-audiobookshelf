"""Sensor platform for Audiobookshelf."""
import logging
from .const import DOMAIN
from .entity import AudiobookshelfEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_devices([AudiobookshelfSensor(coordinator, entry)])


class AudiobookshelfSensor(AudiobookshelfEntity):
    """audiobookshelf Sensor class."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_sessions"

    @property
    def state(self):
        """Return the state of the sensor."""
        try:
            coordinator_get = self.coordinator.data.get(
                "sessions", ""
            )  # need to work out how to add functionality to the coordinator to fetch /api/users
            _LOGGER.info("""sensor coordinator got: %s""", coordinator_get)
            if isinstance(coordinator_get, int):
                return coordinator_get
            return None
        except Exception as exception:  # pylint: disable=broad-exception-caught
            _LOGGER.info("""sensor caught error on is_on: %s""", exception)
            return None

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:format-quote-close"

    @property
    def device_class(self):
        """Return de device class of the sensor."""
        return "audiobookshelf__custom_device_class"
