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
    UserProgress,
)
from custom_components.audiobookshelf.const import DATA_COORDINATOR, DOMAIN, VERSION

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
        icon="mdi:account-multiple-outline",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="users",
    ),
    AudiobookShelfSensorEntityDescription(
        key="count_users_online",
        name="Audiobookshelf Users Online",
        icon="mdi:account-multiple",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="users",
    ),
    AudiobookShelfSensorEntityDescription(
        key="count_open_sessions",
        name="Audiobookshelf Open Sessions",
        icon="mdi:account-music-outline",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="sessions",
    ),
    AudiobookShelfSensorEntityDescription(
        key="count_recent_sessions",
        name="Audiobookshelf Recent Sessions",
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

    coordinator: AudiobookShelfDataUpdateCoordinator = hass.data[DOMAIN][DATA_COORDINATOR]

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

    entities: list = [
        AudiobookShelfSensor(coordinator, sensor_description)
        for sensor_description in sensors_descriptions
    ]

    entities.append(AudiobookShelfRecentlyAddedSensor(coordinator))

    existing_users: set[str] = set()

    def _sync_user_progress_entities() -> None:
        user_progress_list: list[UserProgress] = (
            coordinator.data.get("user_progress", []) if coordinator.data else []
        )
        new_entities = []
        for up in user_progress_list:
            if up.user_id not in existing_users:
                existing_users.add(up.user_id)
                new_entities.append(
                    AudiobookShelfUserProgressSensor(coordinator, up.user_id, up.username)
                )
        if new_entities:
            async_add_entities(new_entities)

    _sync_user_progress_entities()
    coordinator.async_add_listener(_sync_user_progress_entities)

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
        url = self.coordinator.api_url
        key = self.entity_description.key
        key_context = self.entity_description.key_context
        key_context_method = self.entity_description.key_context_method
        return f"{url}_{key}_{key_context}_{key_context_method}"


class AudiobookShelfRecentlyAddedSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the most recently added item across all libraries."""

    coordinator: AudiobookShelfDataUpdateCoordinator
    _attr_icon = "mdi:book-plus"
    _attr_name = "Audiobookshelf Recently Added"

    def __init__(self, coordinator: AudiobookShelfDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, None)

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self.coordinator.api_url}_recently_added"

    @property
    def native_value(self) -> str | None:
        """Return the title of the most recently added item."""
        items = self.coordinator.data.get("recently_added", [])
        if items:
            return items[0].get("title")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return full recently added list as attributes."""
        return {"items": self.coordinator.data.get("recently_added", [])}

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.api_url)},
            "name": "Audiobookshelf",
            "manufacturer": "advplyr",
            "sw_version": VERSION,
            "configuration_url": self.coordinator.api_url,
        }


class AudiobookShelfUserProgressSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the current reading progress for a specific user."""

    coordinator: AudiobookShelfDataUpdateCoordinator
    _attr_icon = "mdi:book-open-page-variant"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: AudiobookShelfDataUpdateCoordinator,
        user_id: str,
        username: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, None)
        self._user_id = user_id
        self._username = username
        self._attr_name = f"Audiobookshelf {username} Progress"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self.coordinator.api_url}_user_progress_{self._user_id}"

    def _get_user_progress(self) -> UserProgress | None:
        """Find this user's progress from coordinator data."""
        for p in self.coordinator.data.get("user_progress", []):
            if p.user_id == self._user_id:
                return p
        return None

    @property
    def native_value(self) -> float | None:
        """Return progress as a percentage."""
        progress = self._get_user_progress()
        if progress is None:
            return None
        if progress.progress is None:
            return 0.0
        return round(progress.progress * 100, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return full progress details as attributes."""
        progress = self._get_user_progress()
        if not progress:
            return {}
        return {
            "username": progress.username,
            "item_id": progress.item_id,
            "current_time_seconds": progress.current_time,
            "duration_seconds": progress.duration,
            "is_finished": progress.is_finished,
        }

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.api_url)},
            "name": "Audiobookshelf",
            "manufacturer": "advplyr",
            "sw_version": VERSION,
            "configuration_url": self.coordinator.api_url,
        }
