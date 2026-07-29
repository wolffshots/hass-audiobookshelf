"""Tests for how sensors read values out of the coordinator's data."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

from homeassistant.helpers.device_registry import DeviceEntryType

from custom_components.audiobookshelf import sensor as sensor_module
from custom_components.audiobookshelf.const import DOMAIN
from custom_components.audiobookshelf.sensor import (
    SENSOR_DESCRIPTIONS,
    AudiobookShelfSensor,
    AudiobookShelfSensorEntityDescription,
)

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Built per library at runtime, so they are not in SENSOR_DESCRIPTIONS.
LIBRARY_TRANSLATION_KEYS = ("library_size", "library_items", "library_duration")

LIBRARY_SENSOR = AudiobookShelfSensorEntityDescription(
    key="library_stats",
    key_context="lib-1",
    key_context_method="total_items",
    name="Audiobookshelf Books Items",
)
GLOBAL_SENSOR = AudiobookShelfSensorEntityDescription(key="count_users")


def _sensor(
    description: AudiobookShelfSensorEntityDescription, data: dict[str, Any]
) -> AudiobookShelfSensor:
    """Build a sensor over a coordinator holding the given data."""
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.last_update_success = True
    with patch.object(AudiobookShelfSensor, "__init__", return_value=None):
        sensor = AudiobookShelfSensor(coordinator, description)  # type: ignore[call-arg]
    sensor.coordinator = coordinator
    sensor.entity_description = description
    return sensor


def test_library_sensor_reads_its_stat() -> None:
    """A present library reports the requested stat."""
    data = {"library_stats": {"lib-1": SimpleNamespace(total_items=12)}}
    sensor = _sensor(LIBRARY_SENSOR, data)
    assert sensor.native_value == 12
    assert sensor.available is True


def test_library_removed_server_side_does_not_raise() -> None:
    """A library deleted on the server leaves entities behind that must not raise."""
    data: dict[str, Any] = {"library_stats": {"lib-2": SimpleNamespace(total_items=3)}}
    sensor = _sensor(LIBRARY_SENSOR, data)
    assert sensor.native_value is None
    assert sensor.available is False


def test_missing_stat_field_does_not_raise() -> None:
    """A stat dropped from the API response reads as unknown, not an error."""
    data = {"library_stats": {"lib-1": SimpleNamespace()}}
    sensor = _sensor(LIBRARY_SENSOR, data)
    assert sensor.native_value is None


def test_global_sensor_is_unaffected_by_library_stats() -> None:
    """Sensors without a key context ignore the library availability check."""
    sensor = _sensor(GLOBAL_SENSOR, {"count_users": 4, "library_stats": {}})
    assert sensor.native_value == 4
    assert sensor.available is True


def test_identity_is_keyed_on_the_entry_not_the_url() -> None:
    """The URL is user-editable, so identity derived from it orphans entities."""
    coordinator = MagicMock()
    coordinator.api_url = "http://abs.local:13378"
    entry = MagicMock()
    entry.entry_id = "entry-1"

    sensor = AudiobookShelfSensor(coordinator, entry, LIBRARY_SENSOR)

    assert sensor.unique_id == "entry-1_library_stats_lib-1_total_items"
    assert sensor.device_info is not None
    assert sensor.device_info["identifiers"] == {(DOMAIN, "entry-1")}
    assert sensor.device_info["entry_type"] is DeviceEntryType.SERVICE
    # Was the integration version, which reads as the server version.
    assert "sw_version" not in sensor.device_info
    assert sensor.has_entity_name is True


def _setup_platform(libraries: list[Any]) -> tuple[Any, list[Any], list[Any]]:
    """Run the platform setup and return the coordinator, listeners and entities."""
    listeners: list[Any] = []
    entities: list[Any] = []

    def _add_listener(callback_fn: Any, context: Any = None) -> Any:  # noqa: ARG001
        """Record the listener the way DataUpdateCoordinator would."""
        listeners.append(callback_fn)
        return lambda: None

    coordinator = MagicMock()
    coordinator.api_url = "http://abs.local:13378"
    coordinator.libraries = libraries
    coordinator.async_add_listener = _add_listener

    entry = MagicMock()
    entry.entry_id = "entry-1"
    entry.data = {}
    entry.runtime_data = coordinator

    asyncio.run(
        sensor_module.async_setup_entry(
            MagicMock(), entry, cast("AddEntitiesCallback", entities.extend)
        )
    )
    return coordinator, listeners, entities


def test_libraries_present_at_setup_get_sensors() -> None:
    """Six global sensors plus three for the one library."""
    _, _, entities = _setup_platform([SimpleNamespace(id_="lib-1", name="Books")])

    assert len(entities) == len(SENSOR_DESCRIPTIONS) + 3


def test_library_added_later_does_not_need_a_reload() -> None:
    """count_libraries counted a new library while it had no sensors of its own."""
    coordinator, listeners, entities = _setup_platform(
        [SimpleNamespace(id_="lib-1", name="Books")]
    )
    before = len(entities)

    coordinator.libraries.append(SimpleNamespace(id_="lib-2", name="Podcasts"))
    for listener in listeners:
        listener()

    assert len(entities) == before + 3
    new_ids = {e.unique_id for e in entities[before:]}
    assert new_ids == {
        "entry-1_library_stats_lib-2_total_size",
        "entry-1_library_stats_lib-2_total_items",
        "entry-1_library_stats_lib-2_total_duration",
    }


def test_unchanged_libraries_are_not_added_twice() -> None:
    """The listener runs on every poll, so it has to be idempotent."""
    _, listeners, entities = _setup_platform(
        [SimpleNamespace(id_="lib-1", name="Books")]
    )
    before = len(entities)

    for _ in range(3):
        for listener in listeners:
            listener()

    assert len(entities) == before


def _entity_translations() -> dict[str, Any]:
    """Load the sensor entity names shipped in en.json."""
    path = Path(sensor_module.__file__).parent / "translations" / "en.json"
    names: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))["entity"][
        "sensor"
    ]
    return names


def test_every_translation_key_has_a_name() -> None:
    """A key with no entry silently yields an entity with no name."""
    names = _entity_translations()
    keys = [d.translation_key for d in SENSOR_DESCRIPTIONS]

    assert all(key is not None for key in keys)
    assert set(keys) <= set(names)
    assert set(LIBRARY_TRANSLATION_KEYS) <= set(names)


def test_library_names_carry_the_placeholder() -> None:
    """Without {library} every library's sensors would share one name."""
    names = _entity_translations()

    for key in LIBRARY_TRANSLATION_KEYS:
        assert "{library}" in names[key]["name"]


def test_none_value_stays_none() -> None:
    """count_auth_sessions is None on pre-2.36.0 servers and must stay unknown."""
    sensor = _sensor(
        AudiobookShelfSensorEntityDescription(key="count_auth_sessions"),
        {"count_auth_sessions": None},
    )
    assert sensor.native_value is None
