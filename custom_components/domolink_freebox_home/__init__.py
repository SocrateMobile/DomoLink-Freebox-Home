"""The DomoLink Freebox Home integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import FreeboxOsClient
from .const import CONF_API_VERSION, CONF_APP_TOKEN, CONF_USE_HTTPS, DOMAIN
from .coordinator import FreeboxHomeCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.COVER,
    Platform.LIGHT,
    Platform.ALARM_CONTROL_PANEL,
    Platform.CAMERA,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.UPDATE,
]


def _get_coordinators(hass: HomeAssistant) -> list[FreeboxHomeCoordinator]:
    return [
        val
        for val in hass.data.get(DOMAIN, {}).values()
        if isinstance(val, FreeboxHomeCoordinator)
    ]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DomoLink Freebox Home from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    client = FreeboxOsClient(
        session=async_get_clientsession(hass),
        host=str(entry.data[CONF_HOST]),
        port=int(entry.data[CONF_PORT]),
        use_https=bool(entry.data.get(CONF_USE_HTTPS, False)),
        app_token=str(entry.data[CONF_APP_TOKEN]),
        api_version=str(entry.data.get(CONF_API_VERSION, "v11")),
    )
    coordinator = FreeboxHomeCoordinator(hass=hass, client=client, entry=entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    if not hass.services.has_service(DOMAIN, "wake_on_lan"):
        async def _handle_wol(call: ServiceCall) -> None:
            for coord in _get_coordinators(hass):
                await coord.client.async_wake_on_lan(
                    mac=call.data["mac"],
                    interface=call.data.get("interface", "pub"),
                )

        async def _handle_guest_wifi(call: ServiceCall) -> None:
            for coord in _get_coordinators(hass):
                await coord.client.async_create_wifi_guest_key(
                    description=call.data.get("description", "Invité Home Assistant"),
                    duration=int(call.data.get("duration", 3600)),
                )

        async def _handle_mark_calls(call: ServiceCall) -> None:
            for coord in _get_coordinators(hass):
                await coord.client.async_mark_calls_read()
                await coord.async_request_refresh()

        hass.services.async_register(
            DOMAIN,
            "wake_on_lan",
            _handle_wol,
            schema=vol.Schema({vol.Required("mac"): str, vol.Optional("interface", default="pub"): str}),
        )
        hass.services.async_register(
            DOMAIN,
            "create_wifi_guest_key",
            _handle_guest_wifi,
            schema=vol.Schema(
                {
                    vol.Optional("description", default="Invité Home Assistant"): str,
                    vol.Optional("duration", default=3600): int,
                }
            ),
        )
        hass.services.async_register(DOMAIN, "mark_calls_read", _handle_mark_calls)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
