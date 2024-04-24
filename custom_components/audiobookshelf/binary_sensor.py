"""Binary sensor platform for Audiobookshelf."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import AudiobookshelfEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup binary_sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AudiobookshelfBinarySensor(coordinator, entry)])


class AudiobookshelfBinarySensor(AudiobookshelfEntity, BinarySensorEntity):
    """audiobookshelf binary_sensor class."""

    _attr_name = f"{DOMAIN} Connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon ="mdi:format-quote-close"
    entity_id = f"{DOMAIN}_connected"

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
