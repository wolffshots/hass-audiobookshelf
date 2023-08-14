"""Constant for the Audiobookshelf integration"""

# Base component constants
from datetime import timedelta

NAME = "Audiobookshelf"
DOMAIN = "audiobookshelf"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "v0.0.3"

ATTRIBUTION = "Server by https://www.audiobookshelf.org/"
ISSUE_URL = "https://github.com/wolffshots/hass-audiobookshelf/issues"

SCAN_INTERVAL = timedelta(seconds=30)

CONF_ACCESS_TOKEN = "access_token"
CONF_HOST = "host"

PLATFORMS = ["binary_sensor", "sensor"]
