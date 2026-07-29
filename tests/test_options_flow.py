"""Tests for reading the scan interval and for the options flow default."""

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest
import voluptuous as vol
from homeassistant.const import CONF_SCAN_INTERVAL

from custom_components.audiobookshelf.config_flow import (
    SCAN_INTERVAL_SELECTOR,
    AudiobookshelfOptionsFlow,
)
from custom_components.audiobookshelf.const import (
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    scan_interval_for,
)


def _entry(data: dict[str, Any], options: dict[str, Any]) -> Any:
    """Build a config entry stub with the given data and options."""
    entry = MagicMock()
    entry.data = data
    entry.options = options
    return entry


def test_options_override_the_original_data() -> None:
    """Changing the interval in options has to win over the setup value."""
    entry = _entry({CONF_SCAN_INTERVAL: 300}, {CONF_SCAN_INTERVAL: 60})
    assert scan_interval_for(entry) == 60


def test_data_is_used_when_no_option_is_set() -> None:
    """Entries created before the options flow existed only have data."""
    entry = _entry({CONF_SCAN_INTERVAL: 120}, {})
    assert scan_interval_for(entry) == 120


def test_default_is_used_when_neither_is_set() -> None:
    """Neither source is guaranteed, and a missing key used to raise."""
    assert scan_interval_for(_entry({}, {})) == DEFAULT_SCAN_INTERVAL


@pytest.mark.parametrize("interval", [0, 1, MIN_SCAN_INTERVAL - 1, -5])
def test_intervals_below_the_floor_are_rejected(interval: int) -> None:
    """A one second poll would hammer the server; cv.positive_int allowed it."""
    with pytest.raises(vol.Invalid):
        SCAN_INTERVAL_SELECTOR(interval)


@pytest.mark.parametrize("interval", [MIN_SCAN_INTERVAL, 300, 3600])
def test_sensible_intervals_are_accepted(interval: int) -> None:
    """The floor must not reject ordinary values."""
    assert SCAN_INTERVAL_SELECTOR(interval) == interval


def test_options_form_defaults_to_the_current_interval() -> None:
    """The form should open showing what is in force, not the built-in default."""
    flow = AudiobookshelfOptionsFlow()
    # OptionsFlow.config_entry returns _config_entry when it is set, otherwise
    # it looks the entry up on hass. That shortcut is marked "for compatibility
    # only - to be removed in 2025.12", so this line is what will need changing
    # when the pinned Home Assistant moves past it. The integration itself only
    # uses the public property and is unaffected.
    flow._config_entry = _entry({CONF_SCAN_INTERVAL: 300}, {CONF_SCAN_INTERVAL: 45})  # noqa: SLF001
    flow.async_show_form = MagicMock(return_value={})  # type: ignore[method-assign]

    asyncio.run(flow.async_step_init())

    schema = flow.async_show_form.call_args.kwargs["data_schema"]
    assert schema({})[CONF_SCAN_INTERVAL] == 45


def test_submitting_options_stores_them() -> None:
    """The submitted value is written to entry options verbatim."""
    flow = AudiobookshelfOptionsFlow()
    flow.async_create_entry = MagicMock(return_value={})  # type: ignore[method-assign]

    asyncio.run(flow.async_step_init({CONF_SCAN_INTERVAL: 90}))

    flow.async_create_entry.assert_called_once_with(data={CONF_SCAN_INTERVAL: 90})
