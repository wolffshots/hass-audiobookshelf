"""Tests for Audiobookshelf sensor."""
from unittest.mock import Mock, patch

import pytest
from _pytest.logging import LogCaptureFixture
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.audiobookshelf.const import (
    DOMAIN,
)
from custom_components.audiobookshelf.sessions_sensor import (
    AudiobookshelfSessionSensor,
    async_setup_entry,
)

from .const import MOCK_CONFIG


@pytest.fixture(name="mock_coordinator")
async def mock_coordinator_fixture() -> Mock:
    """Mock a coordinator for testing."""
    coordinator_mock = Mock()
    coordinator_mock.data = {"sessions": 6}
    mock_coordinator_fixture.last_update_success = True
    return coordinator_mock


@pytest.fixture(name="mock_coordinator_unknown")
async def mock_coordinator_unknown_fixture() -> Mock:
    """Mock a coordinator for testing."""
    coordinator_mock = Mock()
    coordinator_mock.data = {"sessions": "some other type"}
    mock_coordinator_fixture.last_update_success = True
    return coordinator_mock


@pytest.fixture(name="mock_coordinator_error")
async def mock_coordinator_error_fixture() -> None:
    """Mock a coordinator error for testing."""
    with patch(
        "custom_components.audiobookshelf.AudiobookshelfApiClient.api_wrapper",
        side_effect=Exception,
    ):
        yield None


@pytest.mark.asyncio
async def test_sensor_init_entry(
    hass: HomeAssistant,
    mock_coordinator: Mock,
) -> None:
    """Test the initialisation."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="sensors")
    m_add_entities = Mock()
    m_device = AudiobookshelfSessionSensor(
        coordinator=mock_coordinator,
        config_entry=entry,
    )

    hass.data[DOMAIN] = {
        "sensors": {"audiobookshelf_sessions": m_device},
    }

    await async_setup_entry(hass, entry, m_add_entities)
    assert isinstance(
        hass.data[DOMAIN]["sensors"]["audiobookshelf_sessions"],
        AudiobookshelfSessionSensor,
    )
    m_add_entities.assert_called_once()


async def test_sensor_properties(mock_coordinator: Mock) -> None:
    """Test that the sensor returns the correct properties"""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="sensors")
    sensor = AudiobookshelfSessionSensor(
        coordinator=mock_coordinator,
        config_entry=config_entry,
    )
    assert sensor.name == "audiobookshelf_sessions"
    assert sensor.device_class == "audiobookshelf__custom_device_class"
    assert sensor.icon == "mdi:format-quote-close"
    assert sensor.state == 6


async def test_sensor_unknown(mock_coordinator_unknown: Mock) -> None:
    """Test that the sensor returns the correct properties"""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="sensors")
    sensor = AudiobookshelfSessionSensor(
        coordinator=mock_coordinator_unknown,
        config_entry=config_entry,
    )
    assert sensor.state is None


async def test_sensor_error(
    mock_coordinator_error: Mock,
    caplog: LogCaptureFixture,
) -> None:
    """Test for exception handling on exception on coordinator"""
    caplog.clear()
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="sensors")
    sensor = AudiobookshelfSessionSensor(
        coordinator=mock_coordinator_error,
        config_entry=config_entry,
    )
    assert sensor.name == "audiobookshelf_sessions"
    assert sensor.device_class == "audiobookshelf__custom_device_class"
    assert sensor.icon == "mdi:format-quote-close"
    assert sensor.state is None
    assert len(caplog.record_tuples) == 1
    assert (
        "AttributeError caught while accessing coordinator data."
        in caplog.record_tuples[0][2]
    )
