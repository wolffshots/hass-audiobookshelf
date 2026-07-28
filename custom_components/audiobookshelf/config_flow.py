"""Config flow for Audiobookshelf integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aioaudiobookshelf import SessionConfiguration, get_admin_client_by_token
from aioaudiobookshelf.exceptions import AbsAuthError, BadUserError
from aiohttp import ClientError, ClientSession
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL, CONF_URL

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigFlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def validate_config(data: dict[str, Any]) -> dict:
    """Validate the config entries."""
    errors = {}
    if not bool(data[CONF_URL]):
        errors[CONF_URL] = "url_invalid"
    elif not data[CONF_URL].startswith(("http://", "https://")):
        errors[CONF_URL] = "url_protocol_missing"
    if CONF_API_KEY not in data:
        errors[CONF_API_KEY] = "api_key_invalid"
    if not bool(data[CONF_SCAN_INTERVAL]):
        errors[CONF_SCAN_INTERVAL] = "scan_interval_invalid"
    return errors


async def verify_config(data: dict[str, str]) -> dict:
    """Verify the configuration by testing the API connection."""
    try:
        async with ClientSession() as session:
            await get_admin_client_by_token(
                session_config=SessionConfiguration(
                    session=session,
                    url=data[CONF_URL],
                    token=data[CONF_API_KEY],
                    logger=_LOGGER,
                    pagination_items_per_page=30,
                ),
            )
    except BadUserError:
        return {"base": "not_admin"}
    except AbsAuthError:
        return {"base": "api_auth_error"}
    except (ClientError, TimeoutError):
        return {"base": "cannot_connect"}
    else:
        return {}


class AudiobookshelfConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Audiobookshelf."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
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

            await self.async_set_unique_id("Audiobookshelf")
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

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Handle reauthentication when the stored API key stops working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key and validate it against the existing entry."""
        reauth_entry = self._get_reauth_entry()
        errors: dict = {}

        if user_input is not None:
            errors = await verify_config(
                {**reauth_entry.data, CONF_API_KEY: user_input[CONF_API_KEY]}
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )
