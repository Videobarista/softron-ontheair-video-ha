"""Config flow for Softron OnTheAir Video."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    OnTheAirVideoAuthError,
    OnTheAirVideoClient,
    OnTheAirVideoConnectionError,
    OnTheAirVideoError,
)
from .const import (
    CONF_FPS,
    CONF_THUMBNAIL,
    CONF_USE_HTTPS,
    CONF_VERIFY_SSL,
    DEFAULT_FPS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Optional(CONF_USE_HTTPS, default=False): bool,
        vol.Optional(CONF_VERIFY_SSL, default=False): bool,
    }
)


class OnTheAirVideoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            client = OnTheAirVideoClient(
                session=async_get_clientsession(self.hass),
                host=host,
                port=port,
                username=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
                use_https=user_input.get(CONF_USE_HTTPS, False),
                verify_ssl=user_input.get(CONF_VERIFY_SSL, False),
            )

            try:
                await client.async_check_connection()
            except OnTheAirVideoAuthError:
                errors["base"] = "invalid_auth"
            except OnTheAirVideoConnectionError:
                errors["base"] = "cannot_connect"
            except OnTheAirVideoError:
                errors["base"] = "unknown"
            else:
                data = dict(user_input)
                data[CONF_HOST] = host
                title = data.pop(CONF_NAME, DEFAULT_NAME) or DEFAULT_NAME
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OnTheAirVideoOptionsFlow:
        """Return the options flow."""
        return OnTheAirVideoOptionsFlow()


class OnTheAirVideoOptionsFlow(OptionsFlow):
    """Handle the options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Optional(
                    CONF_FPS, default=options.get(CONF_FPS, DEFAULT_FPS)
                ): vol.All(vol.Coerce(float), vol.Range(min=1, max=120)),
                vol.Optional(
                    CONF_THUMBNAIL, default=options.get(CONF_THUMBNAIL, True)
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
