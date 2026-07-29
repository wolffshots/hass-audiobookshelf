"""Module containing the sensor platform for the Audiobookshelf integration."""

from dataclasses import dataclass
from logging import getLogger
from typing import Any, Final

from aioaudiobookshelf.schema.library import Library
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.audiobookshelf import AudiobookshelfConfigEntry, clean_config
from custom_components.audiobookshelf.audiobook_shelf_data_update_coordinator import (
    AudiobookShelfDataUpdateCoordinator,
)
from custom_components.audiobookshelf.entity import device_info_for

_LOGGER = getLogger(__name__)

# Read-only platform: nothing here writes to the server, so there is no reason
# to serialise updates.
PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class AudiobookShelfSensorEntityDescription(SensorEntityDescription):
    """A class that describes custom sensor entities."""

    key_context: str | None = None
    key_context_method: str | None = None


SENSOR_DESCRIPTIONS: Final[tuple[AudiobookShelfSensorEntityDescription, ...]] = (
    AudiobookShelfSensorEntityDescription(
        key="count_users",
        translation_key="count_users",
        icon="mdi:account-multiple-outline",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="users",
    ),
    AudiobookShelfSensorEntityDescription(
        key="count_users_online",
        translation_key="count_users_online",
        icon="mdi:account-multiple",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="users",
    ),
    AudiobookShelfSensorEntityDescription(
        key="count_open_sessions",
        translation_key="count_open_sessions",
        icon="mdi:account-music-outline",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="sessions",
    ),
    AudiobookShelfSensorEntityDescription(
        key="count_recent_sessions",
        translation_key="count_recent_sessions",
        icon="mdi:account-music",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="sessions",
    ),
    AudiobookShelfSensorEntityDescription(
        key="count_auth_sessions",
        translation_key="count_auth_sessions",
        icon="mdi:shield-account-outline",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="sessions",
    ),
    AudiobookShelfSensorEntityDescription(
        key="count_libraries",
        translation_key="count_libraries",
        icon="mdi:bookshelf",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="libraries",
    ),
)


def library_descriptions(
    library: Library,
) -> list[AudiobookShelfSensorEntityDescription]:
    """Build the sensor descriptions for one library."""
    return [
        AudiobookShelfSensorEntityDescription(
            key="library_stats",
            key_context=library.id_,
            key_context_method="total_size",
            translation_key="library_size",
            translation_placeholders={"library": library.name},
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
            translation_key="library_items",
            translation_placeholders={"library": library.name},
            icon="mdi:book-multiple",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="items",
        ),
        AudiobookShelfSensorEntityDescription(
            key="library_stats",
            key_context=library.id_,
            key_context_method="total_duration",
            translation_key="library_duration",
            translation_placeholders={"library": library.name},
            icon="mdi:timer-outline",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="s",
            suggested_unit_of_measurement="h",
            suggested_display_precision=0,
        ),
    ]


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AudiobookshelfConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    _LOGGER.debug("Configuration data: %s", clean_config(entry.data))

    coordinator = entry.runtime_data

    async_add_entities(
        AudiobookShelfSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )

    known_libraries: set[str] = set()

    @callback
    def add_new_libraries() -> None:
        """Create sensors for libraries seen for the first time."""
        # coordinator.libraries is refreshed by library_stats() on every poll,
        # and is populated by the first refresh before this platform is set up.
        # Reading it rather than calling the API keeps platform setup off the
        # network: a failure there leaves the entry loaded with no entities,
        # which also stops polling, since the coordinator only schedules a
        # refresh while it has listeners.
        new = [
            library
            for library in coordinator.libraries
            if library.id_ not in known_libraries
        ]
        if not new:
            return
        known_libraries.update(library.id_ for library in new)
        _LOGGER.debug("Adding sensors for %s new librarie(s)", len(new))
        async_add_entities(
            AudiobookShelfSensor(coordinator, entry, description)
            for library in new
            for description in library_descriptions(library)
        )

    add_new_libraries()
    # A library created on the server was previously counted by
    # count_libraries while never getting sensors of its own until the user
    # reloaded the integration.
    entry.async_on_unload(coordinator.async_add_listener(add_new_libraries))


class AudiobookShelfSensor(CoordinatorEntity, SensorEntity):
    """Representation of a sensor."""

    coordinator: AudiobookShelfDataUpdateCoordinator
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AudiobookShelfDataUpdateCoordinator,
        entry: AudiobookshelfConfigEntry,
        sensor_description: AudiobookShelfSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description: AudiobookShelfSensorEntityDescription = (
            sensor_description
        )
        super().__init__(coordinator, None)
        # Keyed on the entry id rather than the API URL, which the user can
        # edit. Any change to this format needs a matching async_migrate_entry.
        self._attr_unique_id = (
            f"{entry.entry_id}_{sensor_description.key}"
            f"_{sensor_description.key_context}"
            f"_{sensor_description.key_context_method}"
        )
        self._attr_device_info = device_info_for(entry, coordinator)

    @property
    def available(self) -> bool:
        """Return whether the library this sensor tracks still exists."""
        key_context = self.entity_description.key_context
        if key_context is None:
            return super().available
        return super().available and key_context in self.coordinator.data.get(
            self.entity_description.key, {}
        )

    @property
    def native_value(self) -> Any | None:
        """Return the state of the sensor."""
        native_value = self.coordinator.data.get(self.entity_description.key)
        if self.entity_description.key_context is not None and native_value is not None:
            # A library deleted on the server drops out of library_stats while
            # its entities live on, so this lookup has to tolerate a miss.
            native_value = native_value.get(self.entity_description.key_context)
        if (
            self.entity_description.key_context_method is not None
            and native_value is not None
        ):
            native_value = getattr(
                native_value, self.entity_description.key_context_method, None
            )
        return native_value
