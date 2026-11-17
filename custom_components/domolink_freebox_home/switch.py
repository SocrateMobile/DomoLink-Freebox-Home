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
from .home_helpers import find_endpoint, node_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox Home switch entities."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[FreeboxHomeSwitch] = []
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
