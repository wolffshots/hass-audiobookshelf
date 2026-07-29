"""Tests for how sensors read values out of the coordinator's data."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from custom_components.audiobookshelf.sensor import (
    AudiobookShelfSensor,
    AudiobookShelfSensorEntityDescription,
)

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


def test_none_value_stays_none() -> None:
    """count_auth_sessions is None on pre-2.36.0 servers and must stay unknown."""
    sensor = _sensor(
        AudiobookShelfSensorEntityDescription(key="count_auth_sessions"),
        {"count_auth_sessions": None},
    )
    assert sensor.native_value is None
