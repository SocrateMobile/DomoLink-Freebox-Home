"""Update platform for Freebox Server firmware status."""

from __future__ import annotations

from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreeboxHomeCoordinator
from .home_helpers import box_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox firmware update entity."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.data.update_status or coordinator.data.system.get("firmware_version"):
        async_add_entities([FreeboxFirmwareUpdateEntity(coordinator)])


class FreeboxFirmwareUpdateEntity(
    CoordinatorEntity[FreeboxHomeCoordinator], UpdateEntity
):
    """Firmware update status reported by GET update/."""

    _attr_has_entity_name = True
    _attr_name = "03 · Système · Firmware"
    _attr_icon = "mdi:update"

    def __init__(self, coordinator: FreeboxHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.host}_firmware"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def installed_version(self) -> str | None:
        return (
            self.coordinator.data.update_status.get("current_version")
            or self.coordinator.data.system.get("firmware_version")
        )

    @property
    def latest_version(self) -> str | None:
        upd = self.coordinator.data.update_status
        if upd.get("available"):
            return upd.get("latest_version") or upd.get("version") or self.installed_version
        return self.installed_version
