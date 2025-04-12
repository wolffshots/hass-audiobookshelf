"""Module containing the sensor platform for the Audiobookshelf integration."""

from dataclasses import dataclass
from logging import getLogger
from typing import Any, Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.audiobookshelf import clean_config
from custom_components.audiobookshelf.audiobook_shelf_data_update_coordinator import (
    AudiobookShelfDataUpdateCoordinator,
)
from custom_components.audiobookshelf.const import DOMAIN, VERSION

_LOGGER = getLogger(__name__)


@dataclass(frozen=True)
class AudiobookShelfSensorEntityDescription(SensorEntityDescription):
    """A class that describes custom sensor entities."""

    key_context: str | None = None
    key_context_method: str | None = None


SENSOR_DESCRIPTIONS: Final[tuple[AudiobookShelfSensorEntityDescription, ...]] = (
    AudiobookShelfSensorEntityDescription(
        key="count_users",
        name="Audiobookshelf Users",
        icon="mdi:account-multiple",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="users",
    ),
    AudiobookShelfSensorEntityDescription(
        key="count_open_sessions",
        name="Audiobookshelf Open Sessions",
        icon="mdi:account-music",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="sessions",
    ),
    AudiobookShelfSensorEntityDescription(
        key="count_libraries",
        name="Audiobookshelf Libraries",
        icon="mdi:bookshelf",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="libraries",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    _LOGGER.debug("Configuration data: %s", clean_config(entry.data.copy()))

    coordinator: AudiobookShelfDataUpdateCoordinator = hass.data[DOMAIN]

    sensors_descriptions: list[AudiobookShelfSensorEntityDescription] = []
    sensors_descriptions.extend(SENSOR_DESCRIPTIONS)
    libraries = await coordinator.get_libraries()
    for library in libraries:
        sensors_descriptions.extend(
            [
                AudiobookShelfSensorEntityDescription(
                    key="library_stats",
                    key_context=library.id_,
                    key_context_method="total_size",
                    name=f"Audiobookshelf {library.name} Size",
                    icon="mdi:harddisk",
                    device_class=SensorDeviceClass.DATA_SIZE,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=UnitOfInformation.BYTES,
                    suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
                    suggested_display_precision=2,
                ),
                AudiobookShelfSensorEntityDescription(
                    key="library_stats",
                    key_context=library.id_,
                    key_context_method="total_items",
                    name=f"Audiobookshelf {library.name} Items",
                    icon="mdi:book-multiple",
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement="items",
                ),
                AudiobookShelfSensorEntityDescription(
                    key="library_stats",
                    key_context=library.id_,
                    key_context_method="total_duration",
                    name=f"Audiobookshelf {library.name} Duration",
                    icon="mdi:timer-outline",
                    device_class=SensorDeviceClass.DURATION,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement="s",
                    suggested_unit_of_measurement="h",
                    suggested_display_precision=0,
                ),
            ]
        )
    entities = [
        AudiobookShelfSensor(coordinator, sensor_description)
        for sensor_description in sensors_descriptions
    ]
    async_add_entities(entities)


class AudiobookShelfSensor(CoordinatorEntity, SensorEntity):
    """Representation of a sensor."""

    coordinator: AudiobookShelfDataUpdateCoordinator

    def __init__(
        self,
        coordinator: AudiobookShelfDataUpdateCoordinator,
        sensor_description: AudiobookShelfSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description: AudiobookShelfSensorEntityDescription = (
            sensor_description
        )
        super().__init__(coordinator, None)

    @property
    def native_value(self) -> Any | None:
        """Return the state of the sensor."""
        native_value = self.coordinator.data.get(self.entity_description.key)
        if self.entity_description.key_context is not None and native_value is not None:
            native_value = native_value[self.entity_description.key_context]
        if self.entity_description.key_context_method is not None:
            native_value = getattr(
                native_value, self.entity_description.key_context_method
            )
        return native_value

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.api_url)},
            "name": "Audiobookshelf",
            "manufacturer": "advplyr",
            "sw_version": VERSION,
            "configuration_url": self.coordinator.api_url,
        }

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        # Create unique IDs for each sensor that include the API URL
        url = self.coordinator.api_url
        key = self.entity_description.key
        key_context = self.entity_description.key_context
        key_context_method = self.entity_description.key_context_method
        return f"{url}_{key}_{key_context}_{key_context_method}"
