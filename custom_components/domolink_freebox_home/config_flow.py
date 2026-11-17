"""Config flow for DomoLink Freebox Home."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FreeboxOsClient, FreeboxOsError
from .const import (
    CONF_API_VERSION,
    CONF_APP_TOKEN,
    CONF_USE_HTTPS,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_USE_HTTPS,
    DOMAIN,
)


class FreeboxHomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Freebox OS + Home physical LCD pairing config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str = DEFAULT_HOST
        self._port: int = DEFAULT_PORT
        self._use_https: bool = DEFAULT_USE_HTTPS
        self._api_version: str = "v11"
        self._box_name: str = "Freebox"
        self._box_uid: str = ""
        self._app_token: str = ""
        self._track_id: int = 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = str(user_input[CONF_HOST]).strip()
            self._port = int(user_input[CONF_PORT])
            self._use_https = bool(user_input[CONF_USE_HTTPS])

            client = FreeboxOsClient(
                async_get_clientsession(self.hass),
                host=self._host,
                port=self._port,
                use_https=self._use_https,
            )
            try:
                version_info = await client.async_get_api_version()
                self._api_version = client.api_version
                self._box_name = str(version_info.get("box_model_name") or "Freebox")
                self._box_uid = str(version_info.get("uid") or self._host)

                await self.async_set_unique_id(self._box_uid)
                self._abort_if_unique_id_configured()

                self._app_token, self._track_id = await client.async_request_authorization()
                return await self.async_step_link()
            except FreeboxOsError:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_USE_HTTPS, default=DEFAULT_USE_HTTPS): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = FreeboxOsClient(
                async_get_clientsession(self.hass),
                host=self._host,
                port=self._port,
                use_https=self._use_https,
                app_token=self._app_token,
                api_version=self._api_version,
            )
            try:
                status = await client.async_track_authorization(self._track_id)
                if status == "granted":
                    await client.async_open_session()
                    return self.async_create_entry(
                        title=self._box_name,
                        data={
                            CONF_HOST: self._host,
                            CONF_PORT: self._port,
                            CONF_USE_HTTPS: self._use_https,
                            CONF_APP_TOKEN: self._app_token,
                            CONF_API_VERSION: self._api_version,
                        },
                    )
                if status == "pending":
                    errors["base"] = "authorization_pending"
                else:
                    errors["base"] = "authorization_denied"
            except FreeboxOsError:
                errors["base"] = "cannot_connect"

        return self.async_show_form(step_id="link", data_schema=vol.Schema({}), errors=errors)
