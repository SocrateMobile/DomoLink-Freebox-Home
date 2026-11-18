"""Switch platform for Freebox Home controllable boolean endpoints."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreeboxHomeCoordinator
from .home_helpers import box_device_info, find_endpoint, node_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox OS & Home switch entities."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = []

    if "enabled" in coordinator.data.wifi_config:
        entities.append(FreeboxWifiGlobalSwitch(coordinator))

    if "led_strip_enabled" in coordinator.data.lcd:
        entities.append(FreeboxLcdBoolSwitch(coordinator, "led_strip_enabled", "Bandeau LED Freebox", "mdi:led-strip-variant"))
    if "hide_wifi_key" in coordinator.data.lcd:
        entities.append(FreeboxLcdBoolSwitch(coordinator, "hide_wifi_key", "Masquer clé Wi-Fi écran", "mdi:eye-off"))

    for bss in coordinator.data.wifi_bss:
        if isinstance(bss, dict) and bss.get("id"):
            entities.append(FreeboxWifiBssSwitch(coordinator, bss))

    for rep in coordinator.data.repeaters:
        if isinstance(rep, dict) and rep.get("id") is not None and "led_activated" in rep:
            entities.append(FreeboxRepeaterLedSwitch(coordinator, rep))

    profile_names = {
        int(p["id"]): str(p.get("name") or f"Profil {p['id']}")
        for p in coordinator.data.profiles
        if isinstance(p, dict) and p.get("id") is not None
    }
    for ctrl in coordinator.data.network_controls:
        if isinstance(ctrl, dict) and ctrl.get("profile_id") is not None:
            pid = int(ctrl["profile_id"])
            entities.append(
                FreeboxParentalSwitch(coordinator, pid, profile_names.get(pid, f"Profil {pid}"))
            )

    for vpn in coordinator.data.vpn_servers:
        if isinstance(vpn, dict) and vpn.get("name"):
            entities.append(FreeboxVpnSwitch(coordinator, vpn))

    for node_id, node in coordinator.data.nodes.items():
        if str(node.get("category", "")).lower() in ("plug", "switch", "relay"):
            slot = find_endpoint(node, name="switch", ep_type="slot") or find_endpoint(
                node, ep_type="slot"
            )
            if slot and slot.get("id") is not None:
                signal = find_endpoint(node, name="switch", ep_type="signal")
                entities.append(
                    FreeboxHomeSwitch(
                        coordinator,
                        node_id,
                        int(slot["id"]),
                        int(signal["id"]) if signal and signal.get("id") is not None else None,
                    )
                )
    async_add_entities(entities)


class FreeboxWifiGlobalSwitch(CoordinatorEntity[FreeboxHomeCoordinator], SwitchEntity):
    """Switch enabling/disabling global Freebox Wi-Fi."""

    _attr_has_entity_name = True
    _attr_name = "Wi-Fi Freebox"
    _attr_icon = "mdi:wifi"

    def __init__(self, coordinator: FreeboxHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.host}_wifi_global"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def is_on(self) -> bool | None:
        val = self.coordinator.data.wifi_config.get("enabled")
        return bool(val) if val is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_wifi_enabled(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_wifi_enabled(False)
        await self.coordinator.async_request_refresh()


class FreeboxLcdBoolSwitch(CoordinatorEntity[FreeboxHomeCoordinator], SwitchEntity):
    """Switch controlling a boolean setting in GET/PUT lcd/config."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FreeboxHomeCoordinator,
        field: str,
        label: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._field = field
        self._attr_unique_id = f"{coordinator.client.host}_lcd_{field}"
        self._attr_name = label
        self._attr_icon = icon
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def is_on(self) -> bool | None:
        val = self.coordinator.data.lcd.get(self._field)
        return bool(val) if val is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_lcd_config({self._field: True})
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_lcd_config({self._field: False})
        await self.coordinator.async_request_refresh()


class FreeboxWifiBssSwitch(CoordinatorEntity[FreeboxHomeCoordinator], SwitchEntity):
    """Switch enabling/disabling an individual Wi-Fi SSID/BSS."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:wifi-settings"

    def __init__(self, coordinator: FreeboxHomeCoordinator, bss: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._bss_id = str(bss["id"])
        cfg = bss.get("config") if isinstance(bss.get("config"), dict) else {}
        ssid = cfg.get("ssid") or self._bss_id
        self._attr_unique_id = f"{coordinator.client.host}_bss_{self._bss_id}"
        self._attr_name = f"SSID {ssid} ({self._bss_id})"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def is_on(self) -> bool | None:
        for bss in self.coordinator.data.wifi_bss:
            if isinstance(bss, dict) and str(bss.get("id")) == self._bss_id:
                cfg = bss.get("config") if isinstance(bss.get("config"), dict) else {}
                return bool(cfg.get("enabled", False))
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_wifi_bss_enabled(self._bss_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_wifi_bss_enabled(self._bss_id, False)
        await self.coordinator.async_request_refresh()


class FreeboxRepeaterLedSwitch(CoordinatorEntity[FreeboxHomeCoordinator], SwitchEntity):
    """Switch controlling a Wi-Fi repeater LED."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:led-on"

    def __init__(self, coordinator: FreeboxHomeCoordinator, rep: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._rep_id = str(rep["id"])
        self._attr_unique_id = f"repeater_{self._rep_id}_led"
        self._attr_name = f"LED Répéteur {rep.get('name') or self._rep_id}"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def is_on(self) -> bool | None:
        for rep in self.coordinator.data.repeaters:
            if isinstance(rep, dict) and str(rep.get("id")) == self._rep_id:
                return bool(rep.get("led_activated", False))
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_edit_repeater(self._rep_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_edit_repeater(self._rep_id, False)
        await self.coordinator.async_request_refresh()


class FreeboxParentalSwitch(CoordinatorEntity[FreeboxHomeCoordinator], SwitchEntity):
    """Switch allowing/blocking internet access for a Freebox profile."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:account-lock"

    def __init__(
        self, coordinator: FreeboxHomeCoordinator, profile_id: int, profile_name: str
    ) -> None:
        super().__init__(coordinator)
        self._profile_id = profile_id
        self._attr_unique_id = f"parental_{profile_id}"
        self._attr_name = f"Internet {profile_name}"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def is_on(self) -> bool | None:
        for ctrl in self.coordinator.data.network_controls:
            if isinstance(ctrl, dict) and int(ctrl.get("profile_id", -1)) == self._profile_id:
                return str(ctrl.get("current_mode", "allowed")).lower() != "denied"
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_network_control_mode(
            self._profile_id, "allowed"
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_network_control_mode(
            self._profile_id, "denied"
        )
        await self.coordinator.async_request_refresh()


class FreeboxVpnSwitch(CoordinatorEntity[FreeboxHomeCoordinator], SwitchEntity):
    """Switch enabling/disabling a Freebox VPN server."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:shield-lock"

    def __init__(self, coordinator: FreeboxHomeCoordinator, vpn: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._vpn_id = str(vpn["name"])
        self._attr_unique_id = f"vpn_{self._vpn_id}"
        self._attr_name = f"Serveur VPN {self._vpn_id}"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def is_on(self) -> bool | None:
        for vpn in self.coordinator.data.vpn_servers:
            if isinstance(vpn, dict) and str(vpn.get("name")) == self._vpn_id:
                return str(vpn.get("state", "")).lower() == "started"
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_vpn_server_enabled(self._vpn_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_vpn_server_enabled(self._vpn_id, False)
        await self.coordinator.async_request_refresh()


class FreeboxHomeSwitch(CoordinatorEntity[FreeboxHomeCoordinator], SwitchEntity):
    """Switch entity backed by a Freebox Home node slot/signal endpoint."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FreeboxHomeCoordinator,
        node_id: int,
        slot_ep_id: int,
        signal_ep_id: int | None,
    ) -> None:
        super().__init__(coordinator)
        self._node_id = node_id
        self._slot_ep_id = slot_ep_id
        self._signal_ep_id = signal_ep_id
        node = coordinator.data.nodes[node_id]
        self._attr_unique_id = f"switch_{node_id}_{slot_ep_id}"
        self._attr_name = str(node.get("label") or f"Interrupteur {node_id}")
        self._attr_device_info = node_device_info(node)

    @property
    def is_on(self) -> bool | None:
        if self._signal_ep_id is None:
            return None
        node = self.coordinator.data.nodes.get(self._node_id)
        if not node:
            return None
        for ep in node.get("show_endpoints") or node.get("endpoints") or []:
            if isinstance(ep, dict) and int(ep.get("id", -1)) == self._signal_ep_id:
                return bool(ep.get("value"))
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_home_endpoint(
            self._node_id, self._slot_ep_id, True
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_home_endpoint(
            self._node_id, self._slot_ep_id, False
        )
        await self.coordinator.async_request_refresh()
