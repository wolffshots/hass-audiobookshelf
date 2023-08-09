"""Binary sensor platform for Audiobookshelf."""
import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from .const import DOMAIN
from .entity import AudiobookshelfEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup binary_sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_devices([AudiobookshelfBinarySensor(coordinator, entry)])


class AudiobookshelfBinarySensor(AudiobookshelfEntity, BinarySensorEntity):
    """audiobookshelf binary_sensor class."""

    @property
    def name(self):
        """Return the name of the binary_sensor."""
        return f"{DOMAIN}_connected"

    @property
    def device_class(self):
        """Return the class of this binary_sensor."""
        return "connectivity"

    @property
    def is_on(self):
        """Return true if the binary_sensor is on."""
        try:
            coordinator_get = self.coordinator.data.get("connectivity", "").get(
                "success", ""
            )
            _LOGGER.info("""binary_sensor coordinator got: %s""", coordinator_get)
            return (
                isinstance(coordinator_get, bool) and coordinator_get
            )  # in this case it is returning a boolean anyways
        except Exception as exception:  # pylint: disable=broad-exception-caught
            _LOGGER.info("""binary_sensor caught error on is_on: %s""", exception)
            return False
