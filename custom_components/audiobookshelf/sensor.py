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
    async_add_devices([
        AudiobookshelfSessionsSensor(coordinator, entry),
        AudiobookshelfNumberOfLibrariesSensor(coordinator, entry),
    ])


class AudiobookshelfSessionsSensor(AudiobookshelfEntity):
    """audiobookshelf Sessions Sensor class."""

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this entity."""
        return f"{DOMAIN}_sessions"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{DOMAIN} Sessions"

    @property
    def state(self) -> int | None:
        """Return the state of the sensor."""
        try:
            coordinator_get = self.coordinator.data.get(
                "sessions",
                "",
            )
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

class AudiobookshelfNumberOfLibrariesSensor(AudiobookshelfEntity):
    """audiobookshelf Number of Libraries Sensor class."""

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this entity."""
        return f"{DOMAIN}_libraries"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{DOMAIN} Number of Libraries"

    @property
    def state(self) -> int | None:
        """Return the state of the sensor."""
        try:
            coordinator_get: dict | str = self.coordinator.data.get(
                "libraries",
                "",
            )
            _LOGGER.debug("""sensor coordinator got: %s""", coordinator_get)

            if not isinstance(coordinator_get, str):
                # count and return int
                return len(coordinator_get["libraries"])

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
