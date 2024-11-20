"""Custom component for Audiobookshelf."""
import logging
import voluptuous as vol
from homeassistant.helpers import config_validation as cv, discovery

DOMAIN = "audiobookshelf"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required("api_key"): cv.string,
                vol.Required("api_url"): cv.string,
                vol.Optional("scan_interval", default=300): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the Audiobookshelf component."""
    conf = config.get(DOMAIN)
    if conf is None:
        _LOGGER.error(f"No config found for {DOMAIN}!")
        return True
    api_key = conf["api_key"]
    api_url = conf["api_url"]
    scan_interval = conf["scan_interval"]

    _LOGGER.info("API URL: %s", api_url)
    _LOGGER.info("Scan Interval: %s", scan_interval)

    hass.data[DOMAIN] = {
        "api_key": api_key,
        "api_url": api_url,
        "scan_interval": scan_interval,
    }
    # Schedule the setup of sensor platform if needed
    hass.async_create_task(
        discovery.async_load_platform(hass, "sensor", DOMAIN, {}, config)
    )

    return True
