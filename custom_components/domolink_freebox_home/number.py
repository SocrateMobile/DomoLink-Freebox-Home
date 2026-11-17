"""Number platform for Freebox OLED/LCD brightness."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
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
    """Set up Freebox LCD brightness number entity when supported."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    if "brightness" in coordinator.data.lcd:
        async_add_entities([FreeboxLcdBrightnessNumber(coordinator)])


class FreeboxLcdBrightnessNumber(
    CoordinatorEntity[FreeboxHomeCoordinator], NumberEntity
):
    """Number entity controlling Freebox OLED/LCD brightness (0..100%)."""

    _attr_has_entity_name = True
    _attr_name = "Luminosité écran Freebox"
    _attr_native_min_value = 0.0
    _attr_native_max_value = 100.0
    _attr_native_step = 5.0
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:brightness-6"

    def __init__(self, coordinator: FreeboxHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.host}_lcd_brightness"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def native_value(self) -> float | None:
        val = self.coordinator.data.lcd.get("brightness")
        return float(val) if val is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.async_set_lcd_brightness(int(value))
        await self.coordinator.async_request_refresh()
