"""Sensor platform for DomoLink Freebox Home."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfDataRate, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreeboxHomeCoordinator
from .home_helpers import box_device_info, node_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox OS & Home sensors."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        FreeboxRateSensor(coordinator, "rate_down", "Débit descendant"),
        FreeboxRateSensor(coordinator, "rate_up", "Débit montant"),
        FreeboxTempSensor(coordinator),
    ]
    for node_id, node in coordinator.data.nodes.items():
        for ep in node.get("show_endpoints") or node.get("endpoints") or []:
            if (
                isinstance(ep, dict)
                and ep.get("ep_type") == "signal"
                and ep.get("value_type") in ("int", "float", "string")
                and ep.get("name") in ("battery", "temp", "humidity", "luminosity")
            ):
                entities.append(FreeboxHomeNodeSensor(coordinator, node_id, ep))
    async_add_entities(entities)


class FreeboxRateSensor(CoordinatorEntity[FreeboxHomeCoordinator], SensorEntity):
    """WAN download/upload bitrate sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = UnitOfDataRate.MEGABITS_PER_SECOND
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: FreeboxHomeCoordinator, field: str, label: str) -> None:
        super().__init__(coordinator)
        self._field = field
        self._attr_name = label
        self._attr_unique_id = f"{coordinator.client.host}_{field}"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def native_value(self) -> float | None:
        raw = self.coordinator.data.connection.get(self._field)
        if raw is None:
            return None
        return round((float(raw) * 8.0) / 1_000_000.0, 2)


class FreeboxTempSensor(CoordinatorEntity[FreeboxHomeCoordinator], SensorEntity):
    """Freebox Server CPU/box temperature sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Température Freebox"

    def __init__(self, coordinator: FreeboxHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.host}_temp_cpub"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def native_value(self) -> float | None:
        sys_data = self.coordinator.data.system
        for key in ("temp_cpub", "temp_cpum", "temp_sw"):
            if sys_data.get(key) is not None:
                return float(sys_data[key])
        for sensor in sys_data.get("sensors") or []:
            if isinstance(sensor, dict) and sensor.get("value") is not None:
                return float(sensor["value"])
        return None


class FreeboxHomeNodeSensor(CoordinatorEntity[FreeboxHomeCoordinator], SensorEntity):
    """Numeric sensor exposed by a Freebox Home node endpoint (battery, temp, etc.)."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: FreeboxHomeCoordinator,
        node_id: int,
        ep: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._node_id = node_id
        self._ep_id = int(ep["id"])
        ep_name = str(ep.get("name", ""))
        self._attr_unique_id = f"node_{node_id}_ep_{self._ep_id}"
        self._attr_name = str(ep.get("label") or ep_name)
        self._attr_device_info = node_device_info(coordinator.data.nodes[node_id])
        if ep_name == "battery":
            self._attr_device_class = SensorDeviceClass.BATTERY
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif ep_name == "temp":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> Any:
        node = self.coordinator.data.nodes.get(self._node_id)
        if not node:
            return None
        for ep in node.get("show_endpoints") or node.get("endpoints") or []:
            if isinstance(ep, dict) and int(ep.get("id", -1)) == self._ep_id:
                return ep.get("value")
        return None
