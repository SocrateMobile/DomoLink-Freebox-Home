"""Select platform for Freebox LED strip animations (Freebox Ultra)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreeboxHomeCoordinator
from .home_helpers import box_device_info

DEFAULT_ANIMATIONS = [
    "static",
    "breathing",
    "organic",
    "rain",
    "stranger_things",
    "trail",
    "wave",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox LED strip animation selector when supported."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    if "led_strip_animation" in coordinator.data.lcd:
        async_add_entities([FreeboxLedStripAnimationSelect(coordinator)])


class FreeboxLedStripAnimationSelect(
    CoordinatorEntity[FreeboxHomeCoordinator], SelectEntity
):
    """Select entity for Freebox Ultra LED strip animation."""

    _attr_has_entity_name = True
    _attr_name = "03 · Système · Animation bandeau LED"
    _attr_icon = "mdi:led-strip-variant"

    def __init__(self, coordinator: FreeboxHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.host}_led_strip_animation"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def options(self) -> list[str]:
        avail = self.coordinator.data.lcd.get("available_led_strip_animations")
        if isinstance(avail, list) and avail:
            return [str(a) for a in avail]
        return list(DEFAULT_ANIMATIONS)

    @property
    def current_option(self) -> str | None:
        val = self.coordinator.data.lcd.get("led_strip_animation")
        return str(val) if val is not None else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.client.async_set_lcd_config(
            {"led_strip_animation": option}
        )
        await self.coordinator.async_request_refresh()
