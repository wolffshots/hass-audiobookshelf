"""Constants for the Audiobookshelf integration."""

from homeassistant.const import Platform

VERSION = "v0.2.3"
ISSUE_URL = "https://github.com/wolffshots/hass-audiobookshelf/issues"
DOMAIN = "audiobookshelf"
PLATFORMS: list[Platform] = [Platform.SENSOR]
HTTP_OK = 200
HTTP_AUTH_FAILURE = 401
