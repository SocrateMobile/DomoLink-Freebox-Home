"""Cover platform for Freebox Home shutters/stores (Somfy RTS/IO)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
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
    """Set up Freebox Home cover entities."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        FreeboxHomeCover(coordinator, node_id)
        for node_id, node in coordinator.data.nodes.items()
        if str(node.get("category", "")).lower() in ("shutter", "kfb", "cover", "store")
        and (
            find_endpoint(node, name="up", ep_type="slot") is not None
            or find_endpoint(node, name="position_set", ep_type="slot") is not None
        )
    ]
    async_add_entities(entities)


class FreeboxHomeCover(CoordinatorEntity[FreeboxHomeCoordinator], CoverEntity):
    """Cover entity backed by Freebox Home shutter/store endpoints."""

    _attr_has_entity_name = True
    _attr_device_class = CoverDeviceClass.SHUTTER

    def __init__(self, coordinator: FreeboxHomeCoordinator, node_id: int) -> None:
        super().__init__(coordinator)
        self._node_id = node_id
        node = coordinator.data.nodes[node_id]
        self._attr_unique_id = f"cover_{node_id}"
        self._attr_name = str(node.get("label") or f"Volet {node_id}")
        self._attr_device_info = node_device_info(node)

        features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
        )
        if find_endpoint(node, name="position_set", ep_type="slot") is not None:
            features |= CoverEntityFeature.SET_POSITION
        self._attr_supported_features = features

    @property
    def current_cover_position(self) -> int | None:
        node = self.coordinator.data.nodes.get(self._node_id)
        if not node:
            return None
        ep = find_endpoint(node, name="position", ep_type="signal")
        if ep and ep.get("value") is not None:
            return int(ep["value"])
        return None

    @property
    def is_closed(self) -> bool | None:
        pos = self.current_cover_position
        return pos == 0 if pos is not None else None

    async def _async_call_slot(self, name: str, value: Any = True) -> None:
        node = self.coordinator.data.nodes.get(self._node_id)
        if not node:
            return
        ep = find_endpoint(node, name=name, ep_type="slot")
        if ep and ep.get("id") is not None:
            await self.coordinator.client.async_set_home_endpoint(
                self._node_id, int(ep["id"]), value
            )
            await self.coordinator.async_request_refresh()

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._async_call_slot("up", True)

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._async_call_slot("down", True)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._async_call_slot("stop", True)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        pos = int(kwargs[ATTR_POSITION])
        await self._async_call_slot("position_set", pos)
