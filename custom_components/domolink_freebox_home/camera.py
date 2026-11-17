"""Camera platform for Freebox Home."""

from __future__ import annotations

from typing import Any

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import FreeboxHomeCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox Home camera entities."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        FreeboxCameraEntity(coordinator, cam)
        for cam in coordinator.data.cameras
        if isinstance(cam, dict) and cam.get("id") is not None
    ]
    async_add_entities(entities)


class FreeboxCameraEntity(CoordinatorEntity[FreeboxHomeCoordinator], Camera):
    """Freebox Home RTSP/HLS camera entity."""

    _attr_has_entity_name = True
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self, coordinator: FreeboxHomeCoordinator, cam: dict[str, Any]
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._cam_id = str(cam["id"])
        self._attr_unique_id = f"camera_{self._cam_id}"
        self._attr_name = str(cam.get("name") or f"Caméra {self._cam_id}")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"camera_{self._cam_id}")},
            name=self._attr_name,
            manufacturer=MANUFACTURER,
            model="Freebox Camera",
        )

    async def stream_source(self) -> str | None:
        for cam in self.coordinator.data.cameras:
            if str(cam.get("id")) == self._cam_id:
                return cam.get("stream_url") or cam.get("streamUrl")
        return None
