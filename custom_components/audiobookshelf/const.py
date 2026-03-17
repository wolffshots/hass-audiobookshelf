"""Constants for the Audiobookshelf integration."""

from homeassistant.const import Platform

VERSION = "v0.3.0"
DOMAIN = "audiobookshelf"
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.MEDIA_PLAYER]

# Keys used to store both coordinators in hass.data[DOMAIN].
DATA_COORDINATOR = "coordinator"
DATA_MEDIA_PLAYER_COORDINATOR = "media_player_coordinator"
