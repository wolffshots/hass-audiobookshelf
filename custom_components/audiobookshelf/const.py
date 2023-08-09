"""Constant for the Audiobookshelf integration"""

# Base component constants
from datetime import timedelta

NAME = "Audiobookshelf"
DOMAIN = "audiobookshelf"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "v0.0.1"

ATTRIBUTION = "Data provided by http://jsonplaceholder.typicode.com/"
ISSUE_URL = "https://github.com/wolffshots/audiobookshelf/issues"

SCAN_INTERVAL = timedelta(seconds=30)

CONF_ACCESS_TOKEN = "access_token"
CONF_HOST = "host"
