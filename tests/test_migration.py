"""Tests for the v1 to v2 config entry migration."""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from homeassistant.const import CONF_URL

import custom_components.audiobookshelf as integration
from custom_components.audiobookshelf.const import DOMAIN

URL = "http://abs.local:13378"


def _entry(version: int = 1) -> Any:
    """Build a config entry stub at the given schema version."""
    entry = MagicMock()
    entry.version = version
    entry.entry_id = "entry-1"
    entry.data = {CONF_URL: URL}
    return entry


def _migrate(
    entry: Any, unique_ids: list[str], *, device: Any = None
) -> dict[str, Any]:
    """Run the migration over stub registries and return what it touched."""
    registry_entries = [
        SimpleNamespace(entity_id=f"sensor.stub_{index}", unique_id=unique_id)
        for index, unique_id in enumerate(unique_ids)
    ]
    entity_registry = MagicMock()
    device_registry = MagicMock()
    device_registry.async_get_device.return_value = device
    hass = MagicMock()

    with (
        patch.object(integration.er, "async_get", return_value=entity_registry),
        patch.object(
            integration.er,
            "async_entries_for_config_entry",
            return_value=registry_entries,
        ),
        patch.object(integration.dr, "async_get", return_value=device_registry),
    ):
        result = asyncio.run(integration.async_migrate_entry(hass, entry))

    return {
        "result": result,
        "entities": entity_registry.async_update_entity,
        "devices": device_registry.async_update_device,
        "hass": hass,
    }


def test_entity_unique_ids_move_onto_the_entry_id() -> None:
    """v1 keyed entities on the API URL, which the user can edit."""
    outcome = _migrate(_entry(), [f"{URL}_count_users_None_None"])

    assert outcome["result"] is True
    outcome["entities"].assert_called_once_with(
        "sensor.stub_0",
        new_unique_id="entry-1_count_users_None_None",
    )


def test_library_unique_ids_keep_their_suffix() -> None:
    """Only the URL prefix changes, so library and stat stay addressable."""
    outcome = _migrate(_entry(), [f"{URL}_library_stats_lib-1_total_size"])

    outcome["entities"].assert_called_once_with(
        "sensor.stub_0",
        new_unique_id="entry-1_library_stats_lib-1_total_size",
    )


def test_unrecognised_unique_ids_are_left_alone() -> None:
    """An id that does not carry the old prefix must not be rewritten."""
    outcome = _migrate(_entry(), ["entry-1_count_users_None_None", "something-else"])

    outcome["entities"].assert_not_called()


def test_device_identifiers_are_rekeyed() -> None:
    """Rekeying rather than recreating preserves the area and any renaming."""
    outcome = _migrate(_entry(), [], device=SimpleNamespace(id="dev-1"))

    outcome["devices"].assert_called_once_with(
        "dev-1", new_identifiers={(DOMAIN, "entry-1")}
    )


def test_missing_device_is_not_an_error() -> None:
    """A fresh entry that never registered a device still migrates."""
    outcome = _migrate(_entry(), [], device=None)

    assert outcome["result"] is True
    outcome["devices"].assert_not_called()


def test_entry_version_is_bumped() -> None:
    """Without this the migration would run on every restart."""
    entry = _entry()
    outcome = _migrate(entry, [])

    outcome["hass"].config_entries.async_update_entry.assert_called_once_with(
        entry, version=2
    )


def test_already_migrated_entry_is_untouched() -> None:
    """A v2 entry must not be rewritten again."""
    outcome = _migrate(_entry(version=2), [f"{URL}_count_users_None_None"])

    assert outcome["result"] is True
    outcome["entities"].assert_not_called()
    outcome["hass"].config_entries.async_update_entry.assert_not_called()
