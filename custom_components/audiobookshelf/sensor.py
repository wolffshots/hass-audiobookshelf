
import asyncio
import logging
from typing import Any
import aiohttp
from datetime import timedelta
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry, EntityRegistry

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DOMAIN = "audiobookshelf"

async def count_active_users(data: dict) -> int:
    """
    Takes in an object with an array of users
    and counts the active ones minus
    the dummy hass one
    """
    count = 0
    for user in data["users"]:
        if user["isActive"] and user["username"] != "hass":
            if ("token" in user and user["token"] == API_KEY):
                continue  # Skip user with provided access_token
            count += 1
    return count

async def clean_user_attributes(data: dict):
    """
    Removes the token and some extra data from users
    """
    for user in data["users"]:
        user["token"] = "<redacted>"
    return data

async def count_open_sessions(data: dict) -> int:
    """
    Counts the number of open stream sessions
    """
    return len(data["openSessions"])

async def count_libraries(data: dict) -> int:
    """
    Counts the number libraries
    """
    return len(data["libraries"])

async def extract_library_details(data: dict) -> dict:
    details = {}
    for library in data.get('libraries', []):
        details.update({library['id']: {"mediaType": library['mediaType'],"provider": library['provider']}})
    return details

def get_total_duration(total_duration: float):
    """Calculate the total duration in hours and round it to 0 decimal places."""
    return round(total_duration / 60.0 / 60.0, 0)

def get_total_size(total_size: float):
    return round(total_size / 1024.0 / 1024.0 / 1024.0, 2)

async def fetch_library_stats(session, id):
    """Fetch data from a single endpoint."""
    headers = {"Authorization": f"Bearer {API_KEY}"}
    endpoint = f"api/libraries/{id}/stats"
    try:
        async with session.get(f"{API_URL}/{endpoint}", headers=headers) as response:
            if response.status != 200:
                _LOGGER.error(f"Failed to fetch data from {endpoint}, status: {response.status}")
                return None
            return await response.json()
    except Exception as e:
        _LOGGER.error(f"Exception occurred while fetching data from {endpoint}: {e}")
        return None

async def get_library_stats(data: dict) -> dict:
    library_details = await extract_library_details(data)
    async with aiohttp.ClientSession() as session:
        results = {}
        for id in library_details:
            library_stats = await fetch_library_stats(session, id)
            if isinstance(library_stats, Exception):
                _LOGGER.error(f"Error fetching data: {library_stats}")
            else:
                # response for a decent library will be HUGE if we don't pick and choose bits
                summary = {}
                if library_details[id]["mediaType"] == "book":
                    summary.update({"totalAuthors":library_stats["totalAuthors"]})
                    if library_stats["totalAuthors"] is not None:
                        summary.update({"totalAuthors":library_stats["totalAuthors"]})
                    else: 
                        summary.update({"totalAuthors": "0"})
                elif library_details[id]["mediaType"] == "podcast":
                    if library_stats["numAudioTracks"] is not None:
                        summary.update({"numAudioTracks":library_stats["numAudioTracks"]})
                    else: 
                        summary.update({"numAudioTracks": "0"})

                if library_stats["totalItems"] is not None:
                    summary.update({"totalItems":library_stats["totalItems"]})
                else: 
                    summary.update({"totalItems": "0"})

                if library_stats["totalSize"] is not None:
                    summary.update({"totalSize": f"{get_total_size(library_stats["totalSize"])}GB"})
                else: 
                    summary.update({"totalSize": "0 GB"})

                if library_stats["totalDuration"] is not None:
                    summary.update({"totalDuration": f"{get_total_duration(library_stats["totalDuration"])} hours"})
                else: 
                    summary.update({"totalDuration": "0 hours"})

                results.update({id: summary})
        return results

async def do_nothing(data):
    return data

type Sensor = dict[str, Any]

# simple polling sensors
sensors: dict[str, Sensor] = {
    "users": {
        "endpoint": "api/users", 
        "name": "Audiobookshelf Users", 
        "data_function": count_active_users,
        "attributes_function": clean_user_attributes
    },
    "sessions": {
        "endpoint": "api/users/online", 
        "name": "Audiobookshelf Open Sessions", 
        "data_function": count_open_sessions,
        "attributes_function": do_nothing
    },
    "libraries": {
        "endpoint": "api/libraries", 
        "name": "Audiobookshelf Libraries", 
        "data_function": count_libraries,
        "attributes_function": get_library_stats
    },
}

async def async_setup_platform(hass: HomeAssistant, config, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""

    conf = hass.data.get(DOMAIN)
    if conf is None:
        _LOGGER.error("Configuration not found in hass.data")
        return

    global API_URL
    API_URL = conf["api_url"]
    global API_KEY
    API_KEY = conf["api_key"]
    global SCAN_INTERVAL
    SCAN_INTERVAL = timedelta(seconds=conf["scan_interval"])

    coordinator = AudiobookshelfDataUpdateCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()

    entities = [
        AudiobookshelfSensor(coordinator, sensors["users"]),
        AudiobookshelfSensor(coordinator, sensors["sessions"]),
        AudiobookshelfSensor(coordinator, sensors["libraries"])
    ]
    async_add_entities(entities, True)

class AudiobookshelfDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Audiobookshelf data from the API."""

    def __init__(self, hass: HomeAssistant):
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name="audiobookshelf",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        headers = {"Authorization": f"Bearer {API_KEY}"}
        data = {}
        try:
            async with aiohttp.ClientSession() as session:
                for sensor in sensors:
                    async with session.get(f"{API_URL}/{sensors[sensor]["endpoint"]}", headers=headers) as response:
                        if response.status != 200:
                            raise UpdateFailed(f"Error fetching data: {response.status}")
                        data[sensors[sensor]["endpoint"]] = await response.json()
            return data
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error fetching data: {err}")

class AudiobookshelfSensor(Entity):
    """Representation of a sensor."""

    def __init__(self, coordinator: AudiobookshelfDataUpdateCoordinator, sensor: Sensor):
        """Initialize the sensor."""
        self._name = sensor["name"]
        self._endpoint = sensor["endpoint"]
        self.coordinator = coordinator
        self._state = None
        self._attributes = {}
        self._process_data = sensor["data_function"]
        self._process_attributes = sensor["attributes_function"]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def device_info(self):
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, "audiobookshelf_id")},
            "name": "Audiobookshelf",
            "manufacturer": "My Company",
            "model": "My Model",
            "sw_version": "1.0",
        }

    async def async_update(self):
        """Fetch new state data for the sensor."""
        data = self.coordinator.data
        if data:
            endpoint_data = data.get(self._endpoint, {})
            if isinstance(endpoint_data, dict):
                self._attributes.update(await self._process_attributes(endpoint_data))
                self._state = await self._process_data(data = endpoint_data)
            else:
                _LOGGER.error("Expected endpoint_data to be a dictionary, got %s", type(endpoint_data))
                _LOGGER.debug(f"Data: {endpoint_data}")

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

