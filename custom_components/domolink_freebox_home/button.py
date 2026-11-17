"""Button platform for DomoLink Freebox Home."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
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
    """Set up Freebox Server reboot button."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FreeboxRebootButton(coordinator)])


class FreeboxRebootButton(CoordinatorEntity[FreeboxHomeCoordinator], ButtonEntity):
    """Button to reboot the Freebox Server via POST system/reboot/."""

    _attr_has_entity_name = True
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_name = "Redémarrer la Freebox"

    def __init__(self, coordinator: FreeboxHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.host}_reboot"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    async def async_press(self) -> None:
        await self.coordinator.client.async_reboot()
