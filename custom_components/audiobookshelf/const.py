"""Constants for the Audiobookshelf integration."""

from typing import TYPE_CHECKING

from aiohttp import ClientTimeout
from homeassistant.const import CONF_SCAN_INTERVAL, Platform

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

VERSION = "v0.3.0"
DOMAIN = "audiobookshelf"
PLATFORMS: list[Platform] = [Platform.SENSOR]

DEFAULT_SCAN_INTERVAL = 300
# A poll costs one request per library plus five more, so a very short
# interval is a way to hammer your own server by accident.
MIN_SCAN_INTERVAL = 30

# aiohttp defaults to a five minute total timeout per request. A single poll
# issues five requests plus one per library, so a server that accepts
# connections but stops responding can hold a poll open for far longer than
# the scan interval, with no error and no sign of staleness.
REQUEST_TIMEOUT = ClientTimeout(total=30)


def scan_interval_for(entry: "ConfigEntry") -> int:
    """Return the poll interval, preferring options over the original data."""
    # Entries created before the options flow existed only have the value in
    # data, so both the setup path and the options form have to fall back the
    # same way. Kept in one place so they cannot disagree.
    return int(
        entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
    )
