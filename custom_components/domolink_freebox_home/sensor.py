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
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreeboxHomeCoordinator, FreeboxHomeData
from .home_helpers import (
    asset_picture_url,
    box_device_info,
    node_device_info,
    resolve_freebox_model,
    resolve_player_model,
    resolve_repeater_model,
)


def _freeplug_members(data: FreeboxHomeData) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    for net in data.freeplugs:
        if isinstance(net, dict):
            for m in net.get("members") or []:
                if isinstance(m, dict):
                    members.append(m)
    return members


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
    entity_picture_fn: Callable[[FreeboxHomeData], str | None] | None = None


BOX_SENSOR_DESCRIPTIONS: tuple[FreeboxBoxSensorDescription, ...] = (
    FreeboxBoxSensorDescription(
        key="ipv4",
        name="01 · Réseau · Adresse IPv4",
        icon="mdi:ip-network",
        value_fn=lambda d: d.connection.get("ipv4"),
    ),
    FreeboxBoxSensorDescription(
        key="ipv6",
        name="01 · Réseau · Adresse IPv6",
        icon="mdi:ip-network-outline",
        value_fn=lambda d: d.connection.get("ipv6"),
    ),
    FreeboxBoxSensorDescription(
        key="wan_media",
        name="01 · Réseau · Type connexion WAN",
        icon="mdi:fiber-optic",
        value_fn=lambda d: d.connection.get("media"),
    ),
    FreeboxBoxSensorDescription(
        key="bandwidth_down",
        name="01 · Réseau · Débit max descendant",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        icon="mdi:speedometer",
        value_fn=lambda d: round(float(d.connection["bandwidth_down"]) / 1_000_000.0, 1)
        if d.connection.get("bandwidth_down") is not None
        else None,
    ),
    FreeboxBoxSensorDescription(
        key="bandwidth_up",
        name="01 · Réseau · Débit max montant",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        icon="mdi:speedometer-slow",
        value_fn=lambda d: round(float(d.connection["bandwidth_up"]) / 1_000_000.0, 1)
        if d.connection.get("bandwidth_up") is not None
        else None,
    ),
    FreeboxBoxSensorDescription(
        key="bytes_down",
        name="01 · Réseau · Volume téléchargé",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:download-network",
        value_fn=lambda d: _bytes_to_gb(d.connection.get("bytes_down")),
    ),
    FreeboxBoxSensorDescription(
        key="bytes_up",
        name="01 · Réseau · Volume envoyé",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:upload-network",
        value_fn=lambda d: _bytes_to_gb(d.connection.get("bytes_up")),
    ),
    FreeboxBoxSensorDescription(
        key="lan_active_count",
        name="01 · Réseau · Appareils LAN actifs",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:devices",
        value_fn=lambda d: sum(1 for h in d.lan_hosts if isinstance(h, dict) and h.get("active")),
    ),
    FreeboxBoxSensorDescription(
        key="wifi_state",
        name="02 · Wi-Fi · État Wi-Fi",
        icon="mdi:wifi",
        value_fn=lambda d: d.wifi_state.get("state"),
    ),
    FreeboxBoxSensorDescription(
        key="repeater_count",
        name="02 · Wi-Fi · Nombre de répéteurs",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:wifi-star",
        value_fn=lambda d: len(d.repeaters),
        entity_picture_fn=lambda d: asset_picture_url(
            resolve_repeater_model(
                d.repeaters[0] if d.repeaters else None, d.system
            )[1]
        ),
    ),
    FreeboxBoxSensorDescription(
        key="freeplug_count",
        name="02 · Wi-Fi · Nombre de FreePlugs",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:power-plug",
        value_fn=lambda d: len(_freeplug_members(d)),
    ),
    FreeboxBoxSensorDescription(
        key="uptime",
        name="03 · Système · Temps de fonctionnement",
        icon="mdi:clock-outline",
        value_fn=lambda d: d.system.get("uptime"),
        entity_picture_fn=lambda d: asset_picture_url(
            resolve_freebox_model(d.system)[2]
        ),
    ),
    FreeboxBoxSensorDescription(
        key="disk_status",
        name="03 · Système · État disque interne",
        icon="mdi:harddisk",
        value_fn=lambda d: d.system.get("disk_status"),
    ),
    FreeboxBoxSensorDescription(
        key="missed_calls",
        name="04 · Téléphonie · Appels manqués",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:phone-missed",
        value_fn=lambda d: sum(
            1 for c in d.call_logs if isinstance(c, dict) and c.get("type") == "missed" and c.get("new")
        ),
    ),
    FreeboxBoxSensorDescription(
        key="unread_voicemails",
        name="04 · Téléphonie · Messages vocaux",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:voicemail",
        value_fn=lambda d: len(d.voicemails),
    ),
    FreeboxBoxSensorDescription(
        key="phone_count",
        name="04 · Téléphonie · Combinés / Lignes DECT",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:phone-classic",
        value_fn=lambda d: len(d.phones),
    ),
    FreeboxBoxSensorDescription(
        key="vpn_connections",
        name="05 · VPN · Clients connectés",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:vpn",
        value_fn=lambda d: len(d.vpn_connections),
    ),
    FreeboxBoxSensorDescription(
        key="player_count",
        name="07 · TV / Players · Nombre de Players TV",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:television-box",
        value_fn=lambda d: len(d.players),
        entity_picture_fn=lambda d: asset_picture_url(
            resolve_player_model(d.players[0] if d.players else None)[1]
        ),
    ),
    FreeboxBoxSensorDescription(
        key="pvr_programmed_count",
        name="07 · TV / Players · Enregistrements programmés",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:record-rec",
        value_fn=lambda d: len(d.pvr_programmed),
    ),
    FreeboxBoxSensorDescription(
        key="pvr_finished_count",
        name="07 · TV / Players · Enregistrements terminés",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:filmstrip",
        value_fn=lambda d: len(d.pvr_finished),
    ),
    FreeboxBoxSensorDescription(
        key="vm_count",
        name="08 · Machines Virtuelles · Nombre de VMs",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:server",
        value_fn=lambda d: len(d.vms),
    ),
    FreeboxBoxSensorDescription(
        key="downloads_active",
        name="09 · Téléchargements · Tâches actives",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:download-multiple",
        value_fn=lambda d: d.download_stats.get("nb_tasks_active", 0)
        if d.download_stats
        else 0,
    ),
    FreeboxBoxSensorDescription(
        key="downloads_rx_rate",
        name="09 · Téléchargements · Débit téléchargement",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:download",
        value_fn=lambda d: round(float(d.download_stats["rx_rate"]) * 8.0 / 1_000_000.0, 2)
        if d.download_stats.get("rx_rate") is not None
        else 0.0,
    ),
    FreeboxBoxSensorDescription(
        key="downloads_tx_rate",
        name="09 · Téléchargements · Débit envoi (Seed)",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:upload",
        value_fn=lambda d: round(float(d.download_stats["tx_rate"]) * 8.0 / 1_000_000.0, 2)
        if d.download_stats.get("tx_rate") is not None
        else 0.0,
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
        FreeboxRateSensor(coordinator, "rate_down", "01 · Réseau · Débit descendant", "mdi:download-network-outline"),
        FreeboxRateSensor(coordinator, "rate_up", "01 · Réseau · Débit montant", "mdi:upload-network-outline"),
        FreeboxTempSensor(coordinator),
        *(FreeboxBoxSensor(coordinator, desc) for desc in BOX_SENSOR_DESCRIPTIONS),
    ]
    for part in coordinator.data.partitions:
        if isinstance(part, dict) and part.get("id") is not None and part.get("total_bytes"):
            entities.append(FreeboxPartitionFreeSensor(coordinator, part))

    if coordinator.data.ftth.get("sfp_pwr_rx") is not None:
        entities.append(FreeboxFtthPowerSensor(coordinator, "sfp_pwr_rx", "01 · Réseau · Signal Fibre Rx"))
    if coordinator.data.ftth.get("sfp_pwr_tx") is not None:
        entities.append(FreeboxFtthPowerSensor(coordinator, "sfp_pwr_tx", "01 · Réseau · Signal Fibre Tx"))

    for disk in coordinator.data.disks:
        if isinstance(disk, dict) and disk.get("id") is not None and disk.get("temp") is not None:
            entities.append(FreeboxDiskTempSensor(coordinator, disk))

    for raid in coordinator.data.raids:
        if isinstance(raid, dict) and raid.get("id") is not None:
            entities.append(FreeboxRaidSensor(coordinator, raid))

    for hw_sensor in coordinator.data.system.get("sensors") or []:
        if isinstance(hw_sensor, dict) and hw_sensor.get("id"):
            entities.append(FreeboxHardwareSensor(coordinator, hw_sensor, is_fan=False))

    for fan in coordinator.data.system.get("fans") or []:
        if isinstance(fan, dict) and fan.get("id"):
            entities.append(FreeboxHardwareSensor(coordinator, fan, is_fan=True))

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

    @property
    def entity_picture(self) -> str | None:
        if self.entity_description.entity_picture_fn is not None:
            return self.entity_description.entity_picture_fn(self.coordinator.data)
        return None


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
        self._attr_name = f"03 · Système · Espace libre {label}"
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


class FreeboxHardwareSensor(CoordinatorEntity[FreeboxHomeCoordinator], SensorEntity):
    """Hardware temperature or fan RPM sensor from GET system/ (sensors[] / fans[])."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: FreeboxHomeCoordinator,
        item: dict[str, Any],
        *,
        is_fan: bool,
    ) -> None:
        super().__init__(coordinator)
        self._hw_id = str(item["id"])
        self._is_fan = is_fan
        self._attr_unique_id = f"{coordinator.client.host}_{'fan' if is_fan else 'temp'}_{self._hw_id}"
        self._attr_name = f"03 · Système · {item.get('name') or self._hw_id}"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )
        if is_fan:
            self._attr_native_unit_of_measurement = "RPM"
            self._attr_icon = "mdi:fan"
        else:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        key = "fans" if self._is_fan else "sensors"
        for item in self.coordinator.data.system.get(key) or []:
            if isinstance(item, dict) and str(item.get("id")) == self._hw_id:
                val = item.get("value")
                return float(val) if val is not None else None
        return None


class FreeboxRateSensor(CoordinatorEntity[FreeboxHomeCoordinator], SensorEntity):
    """WAN download/upload bitrate sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = UnitOfDataRate.MEGABITS_PER_SECOND
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: FreeboxHomeCoordinator,
        field: str,
        label: str,
        icon: str = "mdi:speedometer",
    ) -> None:
        super().__init__(coordinator)
        self._field = field
        self._attr_name = label
        self._attr_icon = icon
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
    _attr_name = "03 · Système · Température principale"
    _attr_icon = "mdi:thermometer"

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


class FreeboxFtthPowerSensor(CoordinatorEntity[FreeboxHomeCoordinator], SensorEntity):
    """FTTH SFP optical signal power sensor (Rx / Tx in dBm)."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:fiber-optic"

    def __init__(self, coordinator: FreeboxHomeCoordinator, field: str, label: str) -> None:
        super().__init__(coordinator)
        self._field = field
        self._attr_unique_id = f"{coordinator.client.host}_{field}"
        self._attr_name = label
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def native_value(self) -> float | None:
        raw = self.coordinator.data.ftth.get(self._field)
        if raw is None:
            return None
        return round(float(raw) / 100.0, 2)


class FreeboxDiskTempSensor(CoordinatorEntity[FreeboxHomeCoordinator], SensorEntity):
    """Physical disk / NVMe SSD temperature sensor from GET storage/disk/."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:harddisk"

    def __init__(self, coordinator: FreeboxHomeCoordinator, disk: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._disk_id = str(disk["id"])
        model = str(disk.get("model") or f"Disque {self._disk_id}").strip()
        self._attr_unique_id = f"{coordinator.client.host}_disk_temp_{self._disk_id}"
        self._attr_name = f"03 · Système · Température Disque {model}"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    @property
    def native_value(self) -> float | None:
        for disk in self.coordinator.data.disks:
            if isinstance(disk, dict) and str(disk.get("id")) == self._disk_id:
                val = disk.get("temp")
                return float(val) if val is not None else None
        return None


class FreeboxRaidSensor(CoordinatorEntity[FreeboxHomeCoordinator], SensorEntity):
    """RAID array health/state sensor from GET storage/raid/."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:nas"

    def __init__(self, coordinator: FreeboxHomeCoordinator, raid: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._raid_id = str(raid["id"])
        name = str(raid.get("name") or f"RAID {self._raid_id}")
        self._attr_unique_id = f"{coordinator.client.host}_raid_{self._raid_id}"
        self._attr_name = f"03 · Système · RAID {name}"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    def _current_raid(self) -> dict[str, Any] | None:
        for raid in self.coordinator.data.raids:
            if isinstance(raid, dict) and str(raid.get("id")) == self._raid_id:
                return raid
        return None

    @property
    def native_value(self) -> str | None:
        raid = self._current_raid()
        return str(raid.get("state")) if raid and raid.get("state") is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        raid = self._current_raid()
        if not raid:
            return {}
        return {
            "level": raid.get("level"),
            "degraded": raid.get("degraded"),
            "sync_progress": raid.get("sync_progress"),
            "total_size": raid.get("total_size"),
        }
