from unittest.mock import Mock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.audiobookshelf.const import DOMAIN, VERSION
from custom_components.audiobookshelf.entity import AudiobookshelfEntity

from .const import MOCK_CONFIG


@pytest.fixture(name="mock_coordinator")
async def mock_coordinator_fixture() -> Mock:
    """Mock a coordinator for testing."""
    coordinator_mock = Mock()
    coordinator_mock.data = {"sessions": 6}
    mock_coordinator_fixture.last_update_success = True
    return coordinator_mock


def test_unique_id(mock_coordinator: Mock) -> None:
    """Test unique id response for entity"""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="audiobookshelf")
    entity = AudiobookshelfEntity(coordinator=mock_coordinator, config_entry=entry)
    assert entity.unique_id == "audiobookshelf"


def test_device_info(mock_coordinator: Mock) -> None:
    """Test device info response for entity"""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="audiobookshelf")
    entity = AudiobookshelfEntity(coordinator=mock_coordinator, config_entry=entry)

    assert entity.device_info == {
        "identifiers": {("audiobookshelf", "audiobookshelf")},
        "manufacturer": "Audiobookshelf",
        "model": VERSION,
        "name": "Audiobookshelf",
    }


def test_device_state_attributes(mock_coordinator: Mock) -> None:
    """Test device state attributes response for entity"""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="audiobookshelf")
    entity = AudiobookshelfEntity(coordinator=mock_coordinator, config_entry=entry)
    assert entity.device_state_attributes == {
        "attribution": "Server by https://www.audiobookshelf.org/",
        "id": "None",
        "integration": DOMAIN,
    }
