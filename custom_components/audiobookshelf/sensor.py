"""Module containing the sensor platform for the Audiobookshelf integration."""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, TypeVar

import aiohttp
from dacite import Config, from_dict
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from custom_components.audiobookshelf import clean_config

_LOGGER = logging.getLogger(__name__)

DOMAIN = "audiobookshelf"
HTTP_OK = 200


def count_active_users(data: dict) -> int:
    """Take in an object with an array of users and counts the active ones."""
    count = 0
    for user in data["users"]:
        if user["isActive"] and user["username"] != "hass":
            if "token" in user and user["token"] == API_KEY:
                continue  # Skip user with provided access_token
            count += 1
    return count


def clean_user_attributes(data: dict) -> dict:
    """Remove the token and some extra data from users."""
    for user in data["users"]:
        user["token"] = "<redacted>"  # noqa: S105
    return data


def count_open_sessions(data: dict) -> int:
    """Count the number of open stream sessions."""
    return len(data["openSessions"])


def count_libraries(data: dict) -> int:
    """Count the number libraries."""
    return len(data["libraries"])


def extract_library_details(data: dict) -> dict:
    """Extract the details from the library."""
    details = {}
    for library in data.get("libraries", []):
        details.update(
            {
                library["id"]: {
                    "mediaType": library["mediaType"],
                    "provider": library["provider"],
                }
            }
        )
    return details


def get_total_duration(total_duration: float | None) -> float | None:
    """Calculate the total duration in hours and round it to 0 decimal places."""
    if total_duration is None:
        return None
    return round(total_duration / 60.0 / 60.0, 0)


def get_total_size(total_size: float | None) -> float | None:
    """Convert the size to human readable."""
    if total_size is None:
        return None
    return round(total_size / 1024.0 / 1024.0 / 1024.0, 2)


def get_library_stats(data: dict) -> dict:
    """Get statistics for each library."""
    return extract_library_details(data)


def do_nothing(data: dict) -> dict:
    """Return the input data without any modifications."""
    return data


type Sensor = dict[str, Any]

# simple polling sensors
sensors: dict[str, Sensor] = {
    "users": {
        "endpoint": "api/users",
        "name": "Audiobookshelf Users",
        "data_function": count_active_users,
        "attributes_function": clean_user_attributes,
        "unit": "users",
    },
    "sessions": {
        "endpoint": "api/users/online",
        "name": "Audiobookshelf Open Sessions",
        "data_function": count_open_sessions,
        "attributes_function": do_nothing,
        "unit": "sessions",
    },
    "libraries": {
        "endpoint": "api/libraries",
        "name": "Audiobookshelf Libraries",
        "data_function": count_libraries,
        "attributes_function": get_library_stats,
        "unit": "libraries",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    conf = entry.data

    _LOGGER.debug("Configuration data: %s", clean_config(conf.copy()))

    global API_URL, API_KEY, SCAN_INTERVAL  # noqa: PLW0603
    API_URL = conf[CONF_URL]
    API_KEY = conf[CONF_API_KEY]
    SCAN_INTERVAL = timedelta(seconds=conf[CONF_SCAN_INTERVAL])

    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {API_KEY}"}
        async with session.get(f"{API_URL}/api/users", headers=headers) as response:
            if response.status != HTTP_OK:
                msg = f"Failed to connect to API: {response.status}"
                _LOGGER.error("%s", msg)
                raise ConfigEntryNotReady(msg)

    coordinator = AudiobookshelfDataUpdateCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()

    libraries = await coordinator.get_libraries()
    coordinator.generate_library_sensors(libraries)

    entities = [
        AudiobookshelfSensor(coordinator, sensor) for sensor in sensors.values()
    ]

    _LOGGER.debug("Sensors: %s", sensors)

    async_add_entities(entities, update_before_add=True)


@dataclass
class LibraryFolder:
    """Class representing a folder in an Audiobookshelf library."""

    id: str
    full_path: str
    library_id: str
    added_at: int | None


@dataclass
class LibrarySettings:
    """Class representing settings for an Audiobookshelf library."""

    cover_aspect_ratio: int | None
    disable_watcher: bool | None
    auto_scan_cron_expression: str | None
    skip_matching_media_with_asin: bool | None
    skip_matching_media_with_isbn: bool | None
    audiobooks_only: bool
    epubs_allow_scripted_content: bool | None
    hide_single_book_series: bool | None
    only_show_later_books_in_continue_series: bool | None
    metadata_precedence: list[str] | None
    mark_as_finished_percent_complete: int | None
    mark_as_finished_time_remaining: int | None


@dataclass
class Library:
    """Class representing an Audiobookshelf library."""

    id: str
    name: str
    folders: list[LibraryFolder] | None
    display_order: int | None
    icon: str | None
    media_type: str
    provider: str | None
    settings: LibrarySettings
    last_scan: int | None
    last_scan_version: str | None
    created_at: int | None
    last_update: int | None


T = TypeVar("T", dict, list)


def camel_to_snake(data: T) -> T:
    """Convert camelCase keys to snake_case."""

    def _convert_key(key: str) -> str:
        return "".join(
            ["_" + char.lower() if char.isupper() else char for char in key]
        ).lstrip("_")

    if isinstance(data, dict):
        return {
            _convert_key(key): camel_to_snake(value)
            if isinstance(value, dict)
            else camel_to_snake(list(value))
            if isinstance(value, list)
            else value
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [
            camel_to_snake(dict(item))
            if isinstance(item, dict)
            else camel_to_snake(list(item))
            if isinstance(item, list)
            else item
            for item in data
        ]
    return data


class AudiobookshelfDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Audiobookshelf data from the API."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name="audiobookshelf",
            update_interval=SCAN_INTERVAL,
        )
        self.libraries = {}

    async def get_libraries(self) -> list[Library]:
        """Fetch library id list from API."""
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {API_KEY}"}
            async with session.get(
                f"{API_URL}/api/libraries", headers=headers
            ) as response:
                if response.status == HTTP_OK:
                    data: dict[str, Any] = await response.json()
                    return [
                        from_dict(
                            data_class=Library,
                            data=(
                                _LOGGER.debug("Converting library: %s", lib)
                                or camel_to_snake(lib)
                            ),
                            config=Config(
                                check_types=False,
                                cast=[str, int],
                            ),
                        )
                        for lib in data["libraries"]
                    ]
        return []

    def generate_library_sensors(self, libraries: list[Library]) -> None:
        """Generate sensor configs for each library."""
        for library in libraries:
            base_id = f"library_{library.id}"
            sensors.update(
                {
                    f"{base_id}_size": {
                        "endpoint": f"api/libraries/{library.id}/stats",
                        "name": f"{library.name} Size",
                        "unique_id": f"{base_id}_size",
                        "data_function": (
                            lambda data: get_total_size(data.get("totalSize"))
                        ),
                        "unit": "GB",
                        "attributes_function": do_nothing,
                    },
                    f"{base_id}_items": {
                        "endpoint": f"api/libraries/{library.id}/stats",
                        "name": f"{library.name} Items",
                        "unique_id": f"{base_id}_items",
                        "data_function": lambda data: data.get("totalItems"),
                        "unit": "items",
                        "attributes_function": do_nothing,
                    },
                    f"{base_id}_duration": {
                        "endpoint": f"api/libraries/{library.id}/stats",
                        "name": f"{library.name} Duration",
                        "unique_id": f"{base_id}_duration",
                        "data_function": (
                            lambda data: get_total_duration(data.get("totalDuration"))
                        ),
                        "unit": "hours",
                        "attributes_function": do_nothing,
                    },
                }
            )

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint."""
        headers = {"Authorization": f"Bearer {API_KEY}"}
        data = {}
        try:
            async with aiohttp.ClientSession() as session:
                for sensor in sensors:
                    async with session.get(
                        f"{API_URL}/{sensors[sensor]["endpoint"]}", headers=headers
                    ) as response:
                        if response.status != HTTP_OK:
                            error_message = f"Error fetching data: {response.status}"
                            raise UpdateFailed(error_message)
                        data[sensors[sensor]["endpoint"]] = await response.json()
                    _LOGGER.debug(
                        "Data returns for %s",
                        f"{API_URL}/{sensors[sensor]["endpoint"]}",
                    )
            return data  # noqa: TRY300
        except aiohttp.ClientError as err:
            msg = "Error fetching data"
            raise UpdateFailed(msg) from err


class AudiobookshelfSensor(Entity):
    """Representation of a sensor."""

    def __init__(
        self, coordinator: AudiobookshelfDataUpdateCoordinator, sensor: Sensor
    ) -> None:
        """Initialize the sensor."""
        self._name = sensor["name"]
        self._unique_id = sensor.get("unique_id", self._name)
        self._unit = sensor.get("unit", None)
        self._endpoint = sensor["endpoint"]
        self.coordinator = coordinator
        self._state = None
        self._attributes = {}
        self._process_data = sensor["data_function"]
        self._process_attributes = sensor["attributes_function"]

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> Any:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attributes

    @property
    def device_info(self) -> dict:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, API_URL)},
            "name": "Audiobookshelf",
            "manufacturer": "advplyr",
            "configuration_url": API_URL,
        }

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        # Create unique IDs for each sensor that include the API URL
        return f"{API_URL}_{self._endpoint}_{self._name}"

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        data = self.coordinator.data
        if data:
            endpoint_data = data.get(self._endpoint, {})
            if isinstance(endpoint_data, dict):
                self._attributes.update(self._process_attributes(endpoint_data))
                new_state = self._process_data(data=endpoint_data)
                if new_state not in (0, None) or self._state in (0, None):
                    self._state = new_state
            else:
                _LOGGER.error(
                    "Expected endpoint_data to be a dictionary, got %s",
                    type(endpoint_data),
                )
                _LOGGER.debug("Data: %s", endpoint_data)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
