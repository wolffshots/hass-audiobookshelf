"""Test Audiobookshelf setup process."""

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.audiobookshelf import (
    AudiobookshelfDataUpdateCoordinator,
    async_reload_entry,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.audiobookshelf.const import (
    DOMAIN,
)

from .const import MOCK_CONFIG

pytest_plugins = "pytest_homeassistant_custom_component"

config_entry = ConfigEntry(
    domain=DOMAIN,
    data=MOCK_CONFIG,
    entry_id="test_entry_id_setup",
    version=1,
    title="Audiobookshelf",
    source="some source",
    minor_version=1,
)

async def test_setup(hass: HomeAssistant)->None:
    assert (await async_setup(hass, MOCK_CONFIG)) is True

async def test_setup_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    aioclient_mock.get("some_host/ping", json={"success": True})
    aioclient_mock.get("some_host/api/users", json={"users": []})
    aioclient_mock.get("some_host/api/users/online", json={"openSessions": []})
    assert await async_setup_entry(hass, config_entry)
    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]
    assert isinstance(
        hass.data["audiobookshelf"]["test_entry_id_setup"],
        AudiobookshelfDataUpdateCoordinator,
    )
    aioclient_mock.clear_requests()

async def test_unload_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    aioclient_mock.get("some_host/ping", json={"success": True})
    aioclient_mock.get("some_host/api/users", json={"users": []})
    aioclient_mock.get("some_host/api/users/online", json={"openSessions": []})
    assert await async_setup_entry(hass, config_entry)
    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]
    assert isinstance(
        hass.data[DOMAIN][config_entry.entry_id],
        AudiobookshelfDataUpdateCoordinator,
    )
    assert await async_unload_entry(hass, config_entry)
    assert config_entry.entry_id not in hass.data[DOMAIN]
    aioclient_mock.clear_requests()


async def test_setup_unload_and_reload_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test entry setup and unload."""
    # Create a mock entry so we don't have to go through config flow
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
    # In this case we are testing the condition where async_setup_entry raises
    # ConfigEntryNotReady using the `error_on_get_data` fixture which simulates
    # an error.
    with pytest.raises(ConfigEntryNotReady):
        assert await async_setup_entry(hass, config_entry)

async def test_setup_entry_connectivity_exception(
    hass: HomeAssistant,
    connectivity_error_on_get_data: None,  # pylint: disable=unused-argument
) -> None:
    """Test connectivity error response when API raises an exception during entry setup."""

    assert await async_setup_entry(hass, config_entry)
    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]
    assert isinstance(
        hass.data[DOMAIN][config_entry.entry_id],
        AudiobookshelfDataUpdateCoordinator,
    )
    assert hass.data[DOMAIN][config_entry.entry_id].data.get("connectivity", "") == "ConnectionError: Unable to connect."
    assert hass.data[DOMAIN][config_entry.entry_id].data.get("users", "") == "ConnectionError: Unable to connect."
    assert hass.data[DOMAIN][config_entry.entry_id].data.get("sessions", "") == "ConnectionError: Unable to connect."

    assert await async_unload_entry(hass, config_entry)
    assert config_entry.entry_id not in hass.data[DOMAIN]

async def test_setup_entry_timeout_exception(
    hass: HomeAssistant,
    timeout_error_on_get_data: None,  # pylint: disable=unused-argument
) -> None:
    """Test timeout error response when API raises an exception during entry setup."""

    assert await async_setup_entry(hass, config_entry)
    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]
    assert isinstance(
        hass.data[DOMAIN][config_entry.entry_id],
        AudiobookshelfDataUpdateCoordinator,
    )
    assert hass.data[DOMAIN][config_entry.entry_id].data.get("connectivity", "") == "TimeoutError: Request timed out."
    assert hass.data[DOMAIN][config_entry.entry_id].data.get("users", "") == "TimeoutError: Request timed out."
    assert hass.data[DOMAIN][config_entry.entry_id].data.get("sessions", "") == "TimeoutError: Request timed out."

    assert await async_unload_entry(hass, config_entry)
    assert config_entry.entry_id not in hass.data[DOMAIN]


async def test_setup_entry_http_exception(
    hass: HomeAssistant,
    http_error_on_get_data: None,  # pylint: disable=unused-argument
) -> None:
    """Test http error response when API raises an exception during entry setup."""

    assert await async_setup_entry(hass, config_entry)
    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]
    assert isinstance(
        hass.data[DOMAIN][config_entry.entry_id],
        AudiobookshelfDataUpdateCoordinator,
    )
    assert hass.data[DOMAIN][config_entry.entry_id].data.get("connectivity", "") == "HTTPError: Generic HTTP Error happened "
    assert hass.data[DOMAIN][config_entry.entry_id].data.get("users", "") == "HTTPError: Generic HTTP Error happened "
    assert hass.data[DOMAIN][config_entry.entry_id].data.get("sessions", "") == "HTTPError: Generic HTTP Error happened "

    assert await async_unload_entry(hass, config_entry)
    assert config_entry.entry_id not in hass.data[DOMAIN]
