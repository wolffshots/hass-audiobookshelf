"""Tests for config validation."""

from typing import Any

from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL, CONF_URL

from custom_components.audiobookshelf.config_flow import validate_config

VALID: dict[str, Any] = {
    CONF_URL: "http://localhost:13378",
    CONF_API_KEY: "abc123",
    CONF_SCAN_INTERVAL: 300,
}


def test_valid_config_has_no_errors() -> None:
    """A fully populated config produces no errors."""
    assert validate_config(dict(VALID)) == {}


def test_https_url_is_accepted() -> None:
    """Https is a valid protocol."""
    assert validate_config({**VALID, CONF_URL: "https://abs.example.com"}) == {}


def test_url_without_protocol_is_rejected() -> None:
    """A url missing http:// or https:// is reported."""
    errors = validate_config({**VALID, CONF_URL: "localhost:13378"})
    assert errors[CONF_URL] == "url_protocol_missing"


def test_empty_url_is_rejected() -> None:
    """An empty url is reported."""
    errors = validate_config({**VALID, CONF_URL: ""})
    assert errors[CONF_URL] == "url_invalid"


def test_missing_api_key_is_rejected() -> None:
    """A config without an api key is reported against the api key field."""
    data = dict(VALID)
    del data[CONF_API_KEY]
    errors = validate_config(data)
    assert errors[CONF_API_KEY] == "api_key_invalid"


def test_empty_url_error_is_not_overwritten() -> None:
    """An empty url reports url_invalid rather than the protocol error."""
    data = dict(VALID)
    del data[CONF_API_KEY]
    errors = validate_config({**data, CONF_URL: ""})
    assert errors[CONF_URL] == "url_invalid"
    assert errors[CONF_API_KEY] == "api_key_invalid"


def test_zero_scan_interval_is_rejected() -> None:
    """A zero scan interval is reported."""
    errors = validate_config({**VALID, CONF_SCAN_INTERVAL: 0})
    assert errors[CONF_SCAN_INTERVAL] == "scan_interval_invalid"
