"""Constants for the Audiobookshelf integration."""

from aiohttp import ClientTimeout
from homeassistant.const import Platform

VERSION = "v0.3.0"
DOMAIN = "audiobookshelf"
PLATFORMS: list[Platform] = [Platform.SENSOR]

# aiohttp defaults to a five minute total timeout per request. A single poll
# issues five requests plus one per library, so a server that accepts
# connections but stops responding can hold a poll open for far longer than
# the scan interval, with no error and no sign of staleness.
REQUEST_TIMEOUT = ClientTimeout(total=30)
