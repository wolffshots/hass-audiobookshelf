"""Sensor platform for Audiobookshelf."""
from .const import DEFAULT_NAME
from .const import DOMAIN
from .const import ICON
from .const import SENSOR
from .entity import AudiobookshelfEntity


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_devices([AudiobookshelfSensor(coordinator, entry)])


class AudiobookshelfSensor(AudiobookshelfEntity):
    """audiobookshelf Sensor class."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DEFAULT_NAME}_{SENSOR}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get("body")

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON

    @property
    def device_class(self):
        """Return de device class of the sensor."""
        return "audiobookshelf__custom_device_class"
