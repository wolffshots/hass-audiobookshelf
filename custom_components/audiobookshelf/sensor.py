"""Sensor platform for Audiobookshelf."""
import logging

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
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_devices([AudiobookshelfSensor(coordinator, entry)])


class AudiobookshelfSensor(AudiobookshelfEntity):
    """audiobookshelf Sensor class."""

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{DOMAIN}_sessions"

    @property
    def state(self) -> int | None:
        """Return the state of the sensor."""
        try:
            coordinator_get = self.coordinator.data.get(
                "sessions",
                "",
            )  # need to work out how to add functionality to the coordinator to fetch /api/users
            _LOGGER.debug("""sensor coordinator got: %s""", coordinator_get)

            if isinstance(coordinator_get, int):
                return coordinator_get

            return None

        except AttributeError:
            _LOGGER.debug(
                "sensor: AttributeError caught while accessing coordinator data.",
            )
            return None

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:format-quote-close"

    @property
    def device_class(self) -> str:
        """Return device class of the sensor."""
        return "audiobookshelf__custom_device_class"
