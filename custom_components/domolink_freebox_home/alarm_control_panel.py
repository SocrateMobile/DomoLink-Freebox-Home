"""Alarm control panel platform for Freebox Home."""

from __future__ import annotations

from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreeboxHomeCoordinator
from .home_helpers import find_endpoint, node_device_info

STATE_MAP: dict[str, AlarmControlPanelState] = {
    "idle": AlarmControlPanelState.DISARMED,
    "disarmed": AlarmControlPanelState.DISARMED,
    "alarm1_arming": AlarmControlPanelState.ARMING,
    "alarm2_arming": AlarmControlPanelState.ARMING,
    "alarm1_armed": AlarmControlPanelState.ARMED_AWAY,
    "alarm2_armed": AlarmControlPanelState.ARMED_HOME,
    "alert": AlarmControlPanelState.TRIGGERED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox Home alarm control panel entities."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        FreeboxAlarmControlPanel(coordinator, node_id)
        for node_id, node in coordinator.data.nodes.items()
        if str(node.get("category", "")).lower() in ("alarm", "alarm_control")
    ]
    async_add_entities(entities)


class FreeboxAlarmControlPanel(
    CoordinatorEntity[FreeboxHomeCoordinator], AlarmControlPanelEntity
):
    """Representation of the Freebox Home Alarm system."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
    )

    def __init__(self, coordinator: FreeboxHomeCoordinator, node_id: int) -> None:
        super().__init__(coordinator)
        self._node_id = node_id
        node = coordinator.data.nodes[node_id]
        self._attr_unique_id = f"alarm_{node_id}"
        self._attr_name = str(node.get("label") or "Alarme Freebox")
        self._attr_device_info = node_device_info(node)

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        node = self.coordinator.data.nodes.get(self._node_id)
        if not node:
            return None
        ep = find_endpoint(node, name="state", ep_type="signal")
        if not ep:
            return None
        raw = str(ep.get("value", "")).lower()
        return STATE_MAP.get(raw)

    async def _async_trigger_slot(self, slot_name: str) -> None:
        node = self.coordinator.data.nodes.get(self._node_id)
        if not node:
            return
        ep = find_endpoint(node, name=slot_name, ep_type="slot")
        if ep and ep.get("id") is not None:
            await self.coordinator.client.async_set_home_endpoint(
                self._node_id, int(ep["id"]), True
            )
            await self.coordinator.async_request_refresh()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        await self._async_trigger_slot("off")

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        await self._async_trigger_slot("alarm1")

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        await self._async_trigger_slot("alarm2")
