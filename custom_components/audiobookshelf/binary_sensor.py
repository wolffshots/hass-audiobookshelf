"""Binary sensor platform for Audiobookshelf."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import AudiobookshelfEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Setup binary_sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_devices([AudiobookshelfBinarySensor(coordinator, entry)])


class AudiobookshelfBinarySensor(AudiobookshelfEntity, BinarySensorEntity):
    """audiobookshelf binary_sensor class."""

    @property
    def name(self) -> str:
        """Return the name of the binary_sensor."""
        return f"{DOMAIN}_connected"

    @property
    def device_class(self) -> str:
        """Return the class of this binary_sensor."""
        return "connectivity"

    @property
    def is_on(self) -> bool:
        """Return true if the binary_sensor is on."""
        try:
            coordinator_get = self.coordinator.data.get("connectivity", "").get(
                "success",
                "",
            )
            _LOGGER.debug("""binary_sensor coordinator got: %s""", coordinator_get)
            return isinstance(coordinator_get, bool) and coordinator_get
        except AttributeError:
            _LOGGER.debug(
                "binary_sensor: AttributeError caught while accessing coordinator data.",
            )
            return False
