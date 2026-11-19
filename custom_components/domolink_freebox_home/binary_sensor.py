"""Binary sensor platform for DomoLink Freebox Home."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreeboxHomeCoordinator
from .home_helpers import (
    box_device_info,
    node_device_info,
    resolve_player_model,
    resolve_repeater_model,
)

CATEGORY_DEVICE_CLASS: dict[str, BinarySensorDeviceClass] = {
    "dws": BinarySensorDeviceClass.DOOR,
    "pir": BinarySensorDeviceClass.MOTION,
    "smoke": BinarySensorDeviceClass.SMOKE,
    "flood": BinarySensorDeviceClass.MOISTURE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox connection, repeater, and Home binary sensors."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = [FreeboxWanBinarySensor(coordinator)]

    for rep in coordinator.data.repeaters:
        if isinstance(rep, dict) and rep.get("id") is not None:
            entities.append(FreeboxRepeaterBinarySensor(coordinator, rep))

    for player in coordinator.data.players:
        if isinstance(player, dict) and player.get("id") is not None:
            entities.append(FreeboxPlayerBinarySensor(coordinator, player))

    for node_id, node in coordinator.data.nodes.items():
        cat = str(node.get("category", "")).lower()
        for ep in node.get("show_endpoints") or node.get("endpoints") or []:
            if (
                isinstance(ep, dict)
                and ep.get("ep_type") == "signal"
                and ep.get("value_type") == "bool"
                and ep.get("name") in ("trigger", "alarm", "cover", "battery_low")
            ):
                entities.append(FreeboxHomeBinarySensor(coordinator, node_id, ep, cat))
    async_add_entities(entities)


class FreeboxWanBinarySensor(CoordinatorEntity[FreeboxHomeCoordinator], BinarySensorEntity):
    """WAN connectivity binary sensor."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "01 · Réseau · Connexion Internet"
    _attr_icon = "mdi:wan"

    def __init__(self, coordinator: FreeboxHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.host}_wan_up"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def is_on(self) -> bool:
        return str(self.coordinator.data.connection.get("state", "")).lower() == "up"


class FreeboxRepeaterBinarySensor(
    CoordinatorEntity[FreeboxHomeCoordinator], BinarySensorEntity
):
    """Wi-Fi repeater connectivity binary sensor."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: FreeboxHomeCoordinator, rep: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._rep_id = str(rep["id"])
        self._attr_unique_id = f"repeater_{self._rep_id}_conn"
        rep_model, _ = resolve_repeater_model(rep, coordinator.data.system)
        gen = "Wi-Fi 7" if "wi-fi 7" in rep_model.lower() else "Wi-Fi 5"
        self._attr_name = f"02 · Wi-Fi · Répéteur {rep.get('name') or self._rep_id} ({gen})"
        self._attr_icon = "mdi:wifi-star"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def is_on(self) -> bool:
        for rep in self.coordinator.data.repeaters:
            if isinstance(rep, dict) and str(rep.get("id")) == self._rep_id:
                return str(rep.get("connection", "")).lower() == "connected"
        return False


class FreeboxPlayerBinarySensor(
    CoordinatorEntity[FreeboxHomeCoordinator], BinarySensorEntity
):
    """Freebox TV Player reachability binary sensor."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:television-box"

    def __init__(self, coordinator: FreeboxHomeCoordinator, player: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._player_id = str(player["id"])
        model_label, _ = resolve_player_model(player)
        self._attr_unique_id = f"player_{self._player_id}_reachable"
        self._attr_name = f"07 · TV / Players · {model_label}"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    def _current_player(self) -> dict[str, Any] | None:
        for player in self.coordinator.data.players:
            if isinstance(player, dict) and str(player.get("id")) == self._player_id:
                return player
        return None

    @property
    def is_on(self) -> bool:
        player = self._current_player()
        return bool(player.get("reachable")) if player else False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        player = self._current_player()
        if not player:
            return {}
        model_label, asset = resolve_player_model(player)
        return {
            "id": player.get("id"),
            "device_model": player.get("device_model"),
            "resolved_model": model_label,
            "mac": player.get("mac"),
            "lan_ip": player.get("lan_ip"),
            "api_version": player.get("api_version"),
            "asset": asset,
        }


class FreeboxHomeBinarySensor(
    CoordinatorEntity[FreeboxHomeCoordinator], BinarySensorEntity
):
    """Binary sensor for Freebox Home detectors (DWS, PIR, Smoke, Tamper)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FreeboxHomeCoordinator,
        node_id: int,
        ep: dict[str, Any],
        node_category: str,
    ) -> None:
        super().__init__(coordinator)
        self._node_id = node_id
        self._ep_id = int(ep["id"])
        ep_name = str(ep.get("name", ""))
        self._attr_unique_id = f"node_{node_id}_ep_{self._ep_id}"
        self._attr_name = str(ep.get("label") or ep_name)
        self._attr_device_info = node_device_info(coordinator.data.nodes[node_id])
        if ep_name == "battery_low":
            self._attr_device_class = BinarySensorDeviceClass.BATTERY
        elif ep_name == "cover":
            self._attr_device_class = BinarySensorDeviceClass.TAMPER
        else:
            self._attr_device_class = CATEGORY_DEVICE_CLASS.get(node_category)

    @property
    def is_on(self) -> bool | None:
        node = self.coordinator.data.nodes.get(self._node_id)
        if not node:
            return None
        for ep in node.get("show_endpoints") or node.get("endpoints") or []:
            if isinstance(ep, dict) and int(ep.get("id", -1)) == self._ep_id:
                val = ep.get("value")
                return bool(val) if val is not None else None
        return None
