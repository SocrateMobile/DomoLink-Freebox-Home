"""Device tracker platform for Freebox LAN hosts."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreeboxHomeCoordinator


def extract_mac(host: dict[str, Any]) -> str | None:
    """Extract normalized MAC address from a Freebox LAN host dict."""
    l2 = host.get("l2ident")
    if isinstance(l2, dict) and l2.get("type") == "mac_address" and l2.get("id"):
        return str(l2["id"]).lower()
    if host.get("mac"):
        return str(host["mac"]).lower()
    return None


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
    """Device tracker for a Freebox LAN host."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FreeboxHomeCoordinator,
        mac: str,
        initial_host: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = f"lan_{mac}"
        self._attr_name = str(
            initial_host.get("primary_name") or initial_host.get("id") or mac
        )

    @property
    def source_type(self) -> SourceType:
        return SourceType.ROUTER

    @property
    def mac_address(self) -> str:
        return self._mac

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
