"""Constants for the Audiobookshelf integration."""

from typing import TYPE_CHECKING

from aiohttp import ClientTimeout
from homeassistant.const import CONF_SCAN_INTERVAL, Platform

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

VERSION = "v0.5.0"
DOMAIN = "audiobookshelf"
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.UPDATE]

DEFAULT_SCAN_INTERVAL = 300
# A poll costs one request per library plus five more, so a very short
# interval is a way to hammer your own server by accident.
MIN_SCAN_INTERVAL = 30

# aiohttp defaults to a five minute total timeout per request. A single poll
# issues five requests plus one per library, so a server that accepts
# connections but stops responding can hold a poll open for far longer than
# the scan interval, with no error and no sign of staleness.
REQUEST_TIMEOUT = ClientTimeout(total=30)

# Audiobookshelf exposes no update-check endpoint of its own - all 112
# documented endpoints were checked - so the only way to answer "is there a
# newer version" is to ask GitHub, as the web UI does from the browser. That
# is the one thing this integration does that leaves the local network, so it
# is off unless the user turns it on.
CONF_CHECK_FOR_UPDATES = "check_for_updates"
DEFAULT_CHECK_FOR_UPDATES = False
GITHUB_LATEST_RELEASE_URL = (
    "https://api.github.com/repos/advplyr/audiobookshelf/releases/latest"
)


def check_for_updates_for(entry: "ConfigEntry") -> bool:
    """Return whether the user has opted in to the GitHub release check."""
    return bool(entry.options.get(CONF_CHECK_FOR_UPDATES, DEFAULT_CHECK_FOR_UPDATES))


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
