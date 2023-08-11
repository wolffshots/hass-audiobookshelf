"""Test Audiobookshelf setup process."""
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.audiobookshelf import (
    AudiobookshelfDataUpdateCoordinator,
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.audiobookshelf.const import (
    DOMAIN,
)

from .const import MOCK_CONFIG

pytest_plugins = "pytest_homeassistant_custom_component"


# In this fixture, we are forcing calls to api_wrapper to raise an Exception. This is useful
# for exception handling.
@pytest.fixture(name="error_on_get_data")
def error_get_data_fixture() -> None:
    """Simulate error when retrieving data from API."""
    with patch(
        "custom_components.audiobookshelf.AudiobookshelfApiClient.api_wrapper",
        side_effect=Exception,
    ):
        yield None


async def test_setup_unload_and_reload_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test entry setup and unload."""
    # Create a mock entry so we don't have to go through config flow
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        entry_id="audiobookshelf",
    )
    aioclient_mock.get("some_host/ping", json={"success": True})
    aioclient_mock.get("some_host/api/users", json={"users": []})
    aioclient_mock.get("some_host/api/users/online", json={"openSessions": []})

    # Set up the entry and assert that the values set during setup are where we expect
    # them to be. Because we have patched the AudiobookshelfDataUpdateCoordinator.async_get_data
    # call, no code from custom_components/audiobookshelf/api.py actually runs.
    assert await async_setup_entry(hass, config_entry)
    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]
    assert isinstance(
        hass.data[DOMAIN][config_entry.entry_id],
        AudiobookshelfDataUpdateCoordinator,
    )

    assert await async_unload_entry(hass, config_entry)
    assert config_entry.entry_id not in hass.data[DOMAIN]

    assert await async_setup_entry(hass, config_entry)
    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]
    assert isinstance(
        hass.data[DOMAIN][config_entry.entry_id],
        AudiobookshelfDataUpdateCoordinator,
    )

    # Reload the entry and assert that the data from above is still there
    assert await async_reload_entry(hass, config_entry) is None
    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]
    assert isinstance(
        hass.data[DOMAIN][config_entry.entry_id],
        AudiobookshelfDataUpdateCoordinator,
    )

    # Unload the entry and verify that the data has been removed
    assert await async_unload_entry(hass, config_entry)
    assert config_entry.entry_id not in hass.data[DOMAIN]

    aioclient_mock.clear_requests()


async def test_setup_entry_exception(
    hass: HomeAssistant,
    error_on_get_data: None,  # pylint: disable=unused-argument
) -> None:
    """Test ConfigEntryNotReady when API raises an exception during entry setup."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")

    # In this case we are testing the condition where async_setup_entry raises
    # ConfigEntryNotReady using the `error_on_get_data` fixture which simulates
    # an error.
    with pytest.raises(ConfigEntryNotReady):
        assert await async_setup_entry(hass, config_entry)
