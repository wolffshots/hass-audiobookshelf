"""Config flow for Audiobookshelf integration."""

from __future__ import annotations

import logging

import aiohttp
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL, CONF_URL

from .const import DOMAIN, HTTP_AUTH_FAILURE, HTTP_OK

_LOGGER = logging.getLogger(__name__)


def validate_config(data: dict[str, str]) -> dict:
    """Validate the config entries."""
    errors = {}
    if not bool(data[CONF_API_KEY]):
        errors[CONF_API_KEY] = "api_key_invalid"
    if not bool(data[CONF_URL]):
        errors[CONF_URL] = "url_invalid"
    if not data[CONF_URL].startswith(("http://", "https://")):
        errors[CONF_URL] = "url_protocol_missing"
    if not bool(data[CONF_SCAN_INTERVAL]):
        errors[CONF_SCAN_INTERVAL] = "scan_interval_invalid"
    return errors


async def verify_config(data: dict) -> dict:
    """Verify the configuration by testing the API connection."""
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {data[CONF_API_KEY]}"}
        try:
            async with session.get(
                f"{data[CONF_URL]}/api/libraries",
                headers=headers,
                timeout=aiohttp.ClientTimeout(5),
            ) as response:
                if response.status != HTTP_OK:
                    msg = f"Failed to connect to API: {response.status}"
                    _LOGGER.error("%s", msg)
                    if response.status == HTTP_AUTH_FAILURE:
                        return {"base": "api_auth_error"}
                    return {"base": "api_other_error"}
                return {}
        except TimeoutError:
            return {"base": "api_timeout_error"}
        except aiohttp.ClientConnectorError:
            return {"base": "api_client_connector_error"}


class AudiobookshelfConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Audiobookshelf."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user step."""
        errors = {}

        if user_input is not None:
            errors.update(validate_config(user_input))
            if not errors:
                errors.update(await verify_config(user_input))
            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                CONF_URL, default=user_input.get(CONF_URL, "")
                            ): str,
                            vol.Required(
                                CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")
                            ): str,
                            vol.Optional(
                                CONF_SCAN_INTERVAL,
                                default=user_input.get(CONF_SCAN_INTERVAL, 300),
                            ): cv.positive_int,
                        }
                    ),
                    errors=errors,
                )

            return self.async_create_entry(
                title="Audiobookshelf",
                data={
                    CONF_URL: user_input[CONF_URL],
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, 300),
                },
            )

        # Show the form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(CONF_SCAN_INTERVAL, default=300): cv.positive_int,
                }
            ),
            errors=errors,
        )
