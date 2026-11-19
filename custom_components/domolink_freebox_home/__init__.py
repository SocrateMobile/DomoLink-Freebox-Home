"""The DomoLink Freebox Home integration."""

from __future__ import annotations

from pathlib import Path
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import FreeboxOsClient
from .const import CONF_API_VERSION, CONF_APP_TOKEN, CONF_USE_HTTPS, DOMAIN
from .coordinator import FreeboxHomeCoordinator
from .home_helpers import ASSETS_URL_BASE, resolve_freebox_model

ASSETS_DIR = Path(__file__).parent / "assets"
_RAW_TITLE_RE = re.compile(r"^(freebox(\s+v\d+)?(\s*\(r\d+\))?|freebox\s+server)$", re.IGNORECASE)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.COVER,
    Platform.LIGHT,
    Platform.ALARM_CONTROL_PANEL,
    Platform.CAMERA,
    Platform.IMAGE,
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


async def _async_register_static_assets(hass: HomeAssistant) -> None:
    """Expose bundled PNG assets under /api/domolink_freebox_home/assets once."""
    if hass.data[DOMAIN].get("_static_registered"):
        return
    http = getattr(hass, "http", None)
    if http is None or not ASSETS_DIR.is_dir():
        return
    try:
        from homeassistant.components.http import StaticPathConfig

        await http.async_register_static_paths(
            [StaticPathConfig(ASSETS_URL_BASE, str(ASSETS_DIR), cache_headers=True)]
        )
    except (ImportError, AttributeError):
        if hasattr(http, "register_static_path"):
            http.register_static_path(ASSETS_URL_BASE, str(ASSETS_DIR), cache_headers=True)
    hass.data[DOMAIN]["_static_registered"] = True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DomoLink Freebox Home from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    await _async_register_static_assets(hass)
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

    # Re-enable any integration-disabled entities (e.g. device_tracker created disabled in v2.0.x)
    ent_reg = er.async_get(hass)
    for ent_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if ent_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
            ent_reg.async_update_entity(ent_entry.entity_id, disabled_by=None)

    # Remove legacy per-MAC devices (lan_*) and refresh Freebox hub name/model + entry title
    dev_reg = dr.async_get(hass)
    box_display_name, _, _ = resolve_freebox_model(coordinator.data.system)
    current_title = str(entry.title or "").strip()
    if (
        not current_title
        or _RAW_TITLE_RE.match(current_title)
        or current_title.lower() == str(entry.data.get(CONF_HOST, "")).lower()
    ) and current_title != box_display_name:
        hass.config_entries.async_update_entry(entry, title=box_display_name)

    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        if any(dom == DOMAIN and ident.startswith("lan_") for dom, ident in device.identifiers):
            dev_reg.async_remove_device(device.id)
        elif any(dom == DOMAIN and ident.startswith("box_") for dom, ident in device.identifiers):
            if device.name != box_display_name or device.model != box_display_name:
                dev_reg.async_update_device(
                    device.id,
                    name=box_display_name,
                    model=box_display_name,
                )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
