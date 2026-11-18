"""Device tracker platform for Freebox LAN hosts."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreeboxHomeCoordinator

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox LAN host device trackers."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    seen: set[str] = set()
    entities: list[FreeboxLanDeviceTracker] = []
    for host in coordinator.data.lan_hosts:
        if not isinstance(host, dict):
            continue
        mac = extract_mac(host)
        if not mac or mac in seen:
            continue
        seen.add(mac)
        entities.append(FreeboxLanDeviceTracker(coordinator, mac, host))
    async_add_entities(entities)


class FreeboxLanDeviceTracker(
    CoordinatorEntity[FreeboxHomeCoordinator], ScannerEntity
):
    """Device tracker for a Freebox LAN host with friendly name + MAC metadata."""

    _attr_has_entity_name = True
    _attr_name = None

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

        friendly_name = resolve_host_name(initial_host, mac)
        vendor = str(initial_host.get("vendor_name") or "").strip() or "Réseau Freebox"
        host_type = str(initial_host.get("host_type") or "").strip()
        model_label = f"{self._mac_upper} · {host_type}" if host_type else self._mac_upper
        box_id = coordinator.data.system.get("mac") or coordinator.client.host

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"lan_{mac}")},
            connections={(CONNECTION_NETWORK_MAC, mac)},
            name=friendly_name,
            manufacturer=vendor,
            model=model_label,
            via_device=(DOMAIN, f"box_{box_id}"),
        )

    @property
    def source_type(self) -> SourceType:
        return SourceType.ROUTER

    @property
    def mac_address(self) -> str:
        return self._mac_upper

    @property
    def hostname(self) -> str | None:
        host = self._find_host()
        if not host:
            return None
        return resolve_host_name(host, self._mac)

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
        return {
            "mac_address": self._mac_upper,
            "ip_address": self.ip_address,
            "vendor": host.get("vendor_name"),
            "host_type": host.get("host_type"),
            "interface": host.get("interface"),
        }
