"""The DomoLink Freebox Home integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
