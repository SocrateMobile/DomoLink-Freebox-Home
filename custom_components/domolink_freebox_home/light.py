"""Light platform for Freebox Home."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
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
    """Set up Freebox Home light entities."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        FreeboxHomeLight(coordinator, node_id)
        for node_id, node in coordinator.data.nodes.items()
        if str(node.get("category", "")).lower() == "light"
    ]
    async_add_entities(entities)


class FreeboxHomeLight(CoordinatorEntity[FreeboxHomeCoordinator], LightEntity):
    """Light entity backed by Freebox Home light endpoints."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FreeboxHomeCoordinator, node_id: int) -> None:
        super().__init__(coordinator)
        self._node_id = node_id
        node = coordinator.data.nodes[node_id]
        self._attr_unique_id = f"light_{node_id}"
        self._attr_name = str(node.get("label") or f"Lumière {node_id}")
        self._attr_device_info = node_device_info(node)
        has_dimmer = find_endpoint(node, name="luminosity", ep_type="slot") is not None
        self._attr_supported_color_modes = (
            {ColorMode.BRIGHTNESS} if has_dimmer else {ColorMode.ONOFF}
        )
        self._attr_color_mode = (
            ColorMode.BRIGHTNESS if has_dimmer else ColorMode.ONOFF
        )

    @property
    def is_on(self) -> bool | None:
        node = self.coordinator.data.nodes.get(self._node_id)
        if not node:
            return None
        ep = find_endpoint(node, name="switch", ep_type="signal")
        return bool(ep.get("value")) if ep and ep.get("value") is not None else None

    @property
    def brightness(self) -> int | None:
        node = self.coordinator.data.nodes.get(self._node_id)
        if not node:
            return None
        ep = find_endpoint(node, name="luminosity", ep_type="signal")
        if ep and ep.get("value") is not None:
            return round(int(ep["value"]) * 255 / 100)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        node = self.coordinator.data.nodes.get(self._node_id)
        if not node:
            return
        if ATTR_BRIGHTNESS in kwargs:
            dim_ep = find_endpoint(node, name="luminosity", ep_type="slot")
            if dim_ep and dim_ep.get("id") is not None:
                pct = round(int(kwargs[ATTR_BRIGHTNESS]) * 100 / 255)
                await self.coordinator.client.async_set_home_endpoint(
                    self._node_id, int(dim_ep["id"]), pct
                )
        sw_ep = find_endpoint(node, name="switch", ep_type="slot")
        if sw_ep and sw_ep.get("id") is not None:
            await self.coordinator.client.async_set_home_endpoint(
                self._node_id, int(sw_ep["id"]), True
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        node = self.coordinator.data.nodes.get(self._node_id)
        if not node:
            return
        sw_ep = find_endpoint(node, name="switch", ep_type="slot")
        if sw_ep and sw_ep.get("id") is not None:
            await self.coordinator.client.async_set_home_endpoint(
                self._node_id, int(sw_ep["id"]), False
            )
            await self.coordinator.async_request_refresh()
