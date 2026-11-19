"""Image platform for DomoLink Freebox Home (Freebox, Repeater, and TV Player photos)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreeboxHomeCoordinator
from .home_helpers import (
    box_device_info,
    resolve_freebox_model,
    resolve_player_model,
    resolve_repeater_model,
)

ASSETS_DIR = Path(__file__).parent / "assets"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox box, Wi-Fi repeater, and TV player photo image entities."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ImageEntity] = [
        FreeboxBoxImageEntity(hass, coordinator),
        FreeboxRepeaterImageEntity(hass, coordinator),
        FreeboxPlayerImageEntity(hass, coordinator),
    ]
    async_add_entities(entities)


class FreeboxBoxImageEntity(CoordinatorEntity[FreeboxHomeCoordinator], ImageEntity):
    """Image entity displaying the studio photo of the detected Freebox model."""

    _attr_has_entity_name = True
    _attr_content_type = "image/png"
    _attr_name = "00 · Aperçu · Photo de la Freebox"
    _attr_icon = "mdi:router-wireless"

    def __init__(self, hass: HomeAssistant, coordinator: FreeboxHomeCoordinator) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = f"{coordinator.client.host}_box_photo"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )
        self._attr_image_last_updated = datetime.now(timezone.utc)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        sys_data = self.coordinator.data.system
        display_name, commercial, asset = resolve_freebox_model(sys_data)
        model_info = sys_data.get("model_info") if isinstance(sys_data.get("model_info"), dict) else {}
        return {
            "display_name": display_name,
            "commercial_name": commercial,
            "board_name": sys_data.get("board_name"),
            "box_flavor": sys_data.get("box_flavor"),
            "model_name": model_info.get("name"),
            "firmware_version": sys_data.get("firmware_version"),
            "asset": asset,
        }

    async def async_image(self) -> bytes | None:
        _, _, asset = resolve_freebox_model(self.coordinator.data.system)
        img_path = ASSETS_DIR / asset
        if not img_path.exists():
            img_path = ASSETS_DIR / "freebox_ultra.png"
        if not img_path.exists():
            return None
        return await self.hass.async_add_executor_job(img_path.read_bytes)


class FreeboxRepeaterImageEntity(CoordinatorEntity[FreeboxHomeCoordinator], ImageEntity):
    """Image entity displaying the Freebox Wi-Fi Repeater photo and count metadata."""

    _attr_has_entity_name = True
    _attr_content_type = "image/png"
    _attr_name = "02 · Wi-Fi · Photo Répéteur Wi-Fi"
    _attr_icon = "mdi:wifi-star"

    def __init__(self, hass: HomeAssistant, coordinator: FreeboxHomeCoordinator) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = f"{coordinator.client.host}_repeater_photo"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )
        self._attr_image_last_updated = datetime.now(timezone.utc)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        reps = [r for r in self.coordinator.data.repeaters if isinstance(r, dict)]
        connected = sum(1 for r in reps if str(r.get("connection", "")).lower() == "connected")
        detailed = []
        wifi7_count = 0
        wifi5_count = 0
        for r in reps:
            label, asset = resolve_repeater_model(r, self.coordinator.data.system)
            if "wi-fi 7" in label.lower():
                wifi7_count += 1
            else:
                wifi5_count += 1
            detailed.append(
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "connection": r.get("connection"),
                    "model": r.get("model"),
                    "resolved_model": label,
                    "asset": asset,
                }
            )
        return {
            "repeater_count": len(reps),
            "connected_count": connected,
            "wifi7_count": wifi7_count,
            "wifi5_count": wifi5_count,
            "repeaters": detailed,
        }

    async def async_image(self) -> bytes | None:
        reps = [r for r in self.coordinator.data.repeaters if isinstance(r, dict)]
        first_rep = reps[0] if reps else None
        _, asset = resolve_repeater_model(first_rep, self.coordinator.data.system)
        img_path = ASSETS_DIR / asset
        if not img_path.exists():
            img_path = ASSETS_DIR / "freebox_repeater.png"
        if not img_path.exists():
            return None
        return await self.hass.async_add_executor_job(img_path.read_bytes)


class FreeboxPlayerImageEntity(CoordinatorEntity[FreeboxHomeCoordinator], ImageEntity):
    """Image entity displaying the studio photo of the detected Freebox TV Player."""

    _attr_has_entity_name = True
    _attr_content_type = "image/png"
    _attr_name = "07 · TV / Players · Photo Player TV"
    _attr_icon = "mdi:television-box"

    def __init__(self, hass: HomeAssistant, coordinator: FreeboxHomeCoordinator) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = f"{coordinator.client.host}_player_photo"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )
        self._attr_image_last_updated = datetime.now(timezone.utc)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        players = [p for p in self.coordinator.data.players if isinstance(p, dict)]
        reachable = sum(1 for p in players if p.get("reachable"))
        detailed = []
        for p in players:
            label, asset = resolve_player_model(p)
            detailed.append(
                {
                    "id": p.get("id"),
                    "device_model": p.get("device_model"),
                    "resolved_model": label,
                    "reachable": bool(p.get("reachable")),
                    "mac": p.get("mac"),
                    "asset": asset,
                }
            )
        return {
            "player_count": len(players),
            "reachable_count": reachable,
            "players": detailed,
        }

    async def async_image(self) -> bytes | None:
        players = [p for p in self.coordinator.data.players if isinstance(p, dict)]
        first_player = players[0] if players else None
        _, asset = resolve_player_model(first_player)
        img_path = ASSETS_DIR / asset
        if not img_path.exists():
            img_path = ASSETS_DIR / "freebox_player_pop.png"
        if not img_path.exists():
            return None
        return await self.hass.async_add_executor_job(img_path.read_bytes)
