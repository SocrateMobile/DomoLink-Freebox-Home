"""Sensor platform for DomoLink Freebox Home."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfDataRate, UnitOfInformation, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreeboxHomeCoordinator, FreeboxHomeData
from .home_helpers import box_device_info, node_device_info


def _bytes_to_gb(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        return round(float(raw) / (1024**3), 2)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, kw_only=True)
class FreeboxBoxSensorDescription(SensorEntityDescription):
    """Describes a Freebox Server hub sensor."""

    value_fn: Callable[[FreeboxHomeData], Any]


BOX_SENSOR_DESCRIPTIONS: tuple[FreeboxBoxSensorDescription, ...] = (
    FreeboxBoxSensorDescription(
        key="ipv4",
        name="Adresse IPv4",
        icon="mdi:ip-network",
        value_fn=lambda d: d.connection.get("ipv4"),
    ),
    FreeboxBoxSensorDescription(
        key="bytes_down",
        name="Volume téléchargé",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:download",
        value_fn=lambda d: _bytes_to_gb(d.connection.get("bytes_down")),
    ),
    FreeboxBoxSensorDescription(
        key="bytes_up",
        name="Volume envoyé",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:upload",
        value_fn=lambda d: _bytes_to_gb(d.connection.get("bytes_up")),
    ),
    FreeboxBoxSensorDescription(
        key="lan_active_count",
        name="Appareils LAN actifs",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:devices",
        value_fn=lambda d: sum(1 for h in d.lan_hosts if isinstance(h, dict) and h.get("active")),
    ),
    FreeboxBoxSensorDescription(
        key="missed_calls",
        name="Appels manqués",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:phone-missed",
        value_fn=lambda d: sum(
            1 for c in d.call_logs if isinstance(c, dict) and c.get("type") == "missed" and c.get("new")
        ),
    ),
    FreeboxBoxSensorDescription(
        key="unread_voicemails",
        name="Messages vocaux",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:voicemail",
        value_fn=lambda d: len(d.voicemails),
    ),
    FreeboxBoxSensorDescription(
        key="vpn_connections",
        name="Clients VPN connectés",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:vpn",
        value_fn=lambda d: len(d.vpn_connections),
    ),
)


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
        *(FreeboxBoxSensor(coordinator, desc) for desc in BOX_SENSOR_DESCRIPTIONS),
    ]
    for part in coordinator.data.partitions:
        if isinstance(part, dict) and part.get("id") is not None and part.get("total_bytes"):
            entities.append(FreeboxPartitionFreeSensor(coordinator, part))

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


class FreeboxBoxSensor(CoordinatorEntity[FreeboxHomeCoordinator], SensorEntity):
    """Generic Freebox Server sensor backed by BOX_SENSOR_DESCRIPTIONS."""

    entity_description: FreeboxBoxSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FreeboxHomeCoordinator,
        description: FreeboxBoxSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.client.host}_{description.key}"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)


class FreeboxPartitionFreeSensor(CoordinatorEntity[FreeboxHomeCoordinator], SensorEntity):
    """Free space percentage sensor for a Freebox storage partition."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:harddisk"

    def __init__(self, coordinator: FreeboxHomeCoordinator, part: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._part_id = str(part["id"])
        label = str(part.get("label") or f"Disque {self._part_id}")
        self._attr_unique_id = f"{coordinator.client.host}_part_{self._part_id}"
        self._attr_name = f"Espace libre {label}"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def native_value(self) -> float | None:
        for part in self.coordinator.data.partitions:
            if isinstance(part, dict) and str(part.get("id")) == self._part_id:
                total = part.get("total_bytes") or 0
                free = part.get("free_bytes")
                if total and free is not None:
                    return round(float(free) * 100.0 / float(total), 1)
        return None


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
