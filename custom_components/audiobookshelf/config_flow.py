"""Adds config flow for Audiobookshelf."""
from __future__ import annotations

import logging
from collections.abc import Coroutine
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import AudiobookshelfApiClient
from .const import CONF_ACCESS_TOKEN, CONF_HOST, DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__package__)


class AudiobookshelfFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for audiobookshelf."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Initialize."""
        self._errors = {}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> Coroutine[Any, Any, Any]:
        """Handle a flow initialized by the user."""
        self._errors = {}

        # Uncomment the next 2 lines if only a single instance of the integration is allowed:
        # if self._async_current_entries():
        #     return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            valid = await self._test_credentials(
                user_input[CONF_HOST],
                user_input[CONF_ACCESS_TOKEN],
            )
            if valid:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )
            self._errors["base"] = "auth"

            return await self._show_config_form(user_input)

        return await self._show_config_form(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AudiobookshelfOptionsFlowHandler:
        return AudiobookshelfOptionsFlowHandler(config_entry)

    async def _show_config_form(
        self,
        user_input: dict[str, Any] | None,  # pylint: disable=unused-argument
    ) -> Coroutine[Any, Any, FlowResult]:
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST): str, vol.Required(CONF_ACCESS_TOKEN): str},
            ),
            errors=self._errors,
        )

    async def _test_credentials(
        self,
        host: str,
        access_token: str,
    ) -> Coroutine[Any, Any, bool]:
        """Return true if credentials is valid."""
        try:
            session = async_create_clientsession(self.hass)
            api = AudiobookshelfApiClient(host, access_token, session)
            response = await api.api_wrapper(
                method="get",
                url=api.get_host() + "/api/users",
            )
            _LOGGER.debug("""test_credentials response was: %s""", response)
            return True
        except (ConnectionError, TimeoutError) as connection_error:
            _LOGGER.debug("Connection or Timeout error: %s", connection_error)
            return False

        except Exception as exception:
            _LOGGER.error("test_credentials failed due to: %s", exception)
            raise


class AudiobookshelfOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options handler for audiobookshelf."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,  # pylint: disable=unused-argument
    ) -> Coroutine[Any, Any, FlowResult]:
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> Coroutine[Any, Any, FlowResult]:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(x, default=self.options.get(x, True)): bool
                    for x in sorted(["binary_sensor", "sensor"])
                },
            ),
        )

    async def _update_options(self) -> Coroutine[Any, Any, FlowResult]:
        """Update config entry options."""
        return self.async_create_entry(
            title=self.config_entry.data.get(CONF_HOST),
            data=self.options,
        )
