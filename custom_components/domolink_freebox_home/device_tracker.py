"""Device tracker platform for Freebox Wi-Fi / LAN clients (grouped under 'Wi-Fi')."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreeboxHomeCoordinator
from .device_signatures import classify_lan_host
from .home_helpers import asset_picture_url, wifi_clients_device_info

_MAC_RE = re.compile(r"^([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$")


def extract_mac(host: dict[str, Any]) -> str | None:
    """Extract normalized MAC address from a Freebox LAN host dict."""
    l2 = host.get("l2ident")
    if isinstance(l2, dict) and l2.get("type") == "mac_address" and l2.get("id"):
        return str(l2["id"]).lower()
    if host.get("mac"):
        return str(host["mac"]).lower()
    return None


def resolve_host_name(host: dict[str, Any], mac: str) -> str:
    """Resolve the best human-readable name for a Freebox LAN host."""
    primary = str(host.get("primary_name") or "").strip()
    if primary and not _MAC_RE.match(primary):
        return primary

    for entry in host.get("names") or []:
        if isinstance(entry, dict):
            candidate = str(entry.get("name") or "").strip()
            if candidate and not _MAC_RE.match(candidate):
                return candidate

    vendor = str(host.get("vendor_name") or "").strip()
    if vendor:
        return f"{vendor} ({mac[-5:].upper()})"

    return mac.upper()


def format_lan_device_label(friendly_name: str, active: bool, mac: str | None = None) -> str:
    """Format LAN client label with green (online) or orange (offline) dot and MAC."""
    dot = "🟢" if active else "🟠"
    if mac and mac.upper() not in friendly_name.upper():
        return f"{dot} {friendly_name} ({mac.upper()})"
    return f"{dot} {friendly_name}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox Wi-Fi/LAN trackers grouped under the 'Wi-Fi' sub-device."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    seen: set[str] = set()
    candidates: list[tuple[bool, str, str, dict[str, Any]]] = []
    for host in coordinator.data.lan_hosts:
        if not isinstance(host, dict):
            continue
        if not host.get("active") and not host.get("persistent"):
            continue
        mac = extract_mac(host)
        if not mac or mac in seen:
            continue
        seen.add(mac)
        friendly = resolve_host_name(host, mac)
        candidates.append((bool(host.get("active")), friendly.lower(), mac, host))

    candidates.sort(key=lambda item: (not item[0], item[1]))
    entities = [
        FreeboxLanDeviceTracker(coordinator, mac, host)
        for _, _, mac, host in candidates
    ]
    async_add_entities(entities)


class FreeboxLanDeviceTracker(
    CoordinatorEntity[FreeboxHomeCoordinator], ScannerEntity
):
    """Device tracker grouped under the 'Wi-Fi' sub-device with status dot, icon, and MAC."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True

    def __init__(
        self,
        coordinator: FreeboxHomeCoordinator,
        mac: str,
        initial_host: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._mac_upper = mac.upper()
        self._attr_unique_id = f"lan_{mac}"
        self._friendly_name = resolve_host_name(initial_host, mac)
        self._attr_device_info = wifi_clients_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def name(self) -> str:
        host = self._find_host()
        if host is not None:
            self._friendly_name = resolve_host_name(host, self._mac)
        return format_lan_device_label(self._friendly_name, self.is_connected, self._mac_upper)

    @property
    def source_type(self) -> SourceType:
        return SourceType.ROUTER

    @property
    def mac_address(self) -> str:
        return self._mac_upper

    @property
    def icon(self) -> str:
        host = self._find_host() or {}
        return classify_lan_host(host, self.is_connected, self.coordinator.data.system).icon

    @property
    def entity_picture(self) -> str | None:
        host = self._find_host() or {}
        info = classify_lan_host(host, self.is_connected, self.coordinator.data.system)
        if info.picture_asset:
            return asset_picture_url(info.picture_asset)
        return None

    @property
    def hostname(self) -> str | None:
        return self._friendly_name

    def _find_host(self) -> dict[str, Any] | None:
        for host in self.coordinator.data.lan_hosts:
            if isinstance(host, dict) and extract_mac(host) == self._mac:
                return host
        return None

    @property
    def is_connected(self) -> bool:
        host = self._find_host()
        return bool(host and host.get("active"))

    @property
    def ip_address(self) -> str | None:
        host = self._find_host()
        if not host:
            return None
        for l3 in host.get("l3connectivities") or []:
            if isinstance(l3, dict) and l3.get("af") == "ipv4" and l3.get("active"):
                return str(l3.get("addr"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        host = self._find_host() or {}
        info = classify_lan_host(host, self.is_connected, self.coordinator.data.system)
        return {
            "status_indicator": "🟢 En ligne" if self.is_connected else "🟠 Hors ligne",
            "brand": info.brand,
            "device_model": info.model,
            "category": info.category,
            "mac_address": self._mac_upper,
            "ip_address": self.ip_address,
            "vendor": host.get("vendor_name"),
            "host_type": host.get("host_type"),
            "interface": host.get("interface"),
        }
