"""Config flow for Audiobookshelf integration."""

from __future__ import annotations

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL, CONF_URL

from .const import DOMAIN


class AudiobookshelfConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Audiobookshelf."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user step."""
        errors = {}

        if user_input is not None:
            # Process user input
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
