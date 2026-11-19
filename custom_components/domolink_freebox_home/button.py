"""Button platform for DomoLink Freebox Home."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreeboxHomeCoordinator
from .home_helpers import box_device_info, resolve_player_model


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox Server, WPS, Telephony, Repeater, Player, and VM buttons."""
    coordinator: FreeboxHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = [
        FreeboxRebootButton(coordinator),
        FreeboxWpsButton(coordinator),
        FreeboxMarkCallsReadButton(coordinator),
        FreeboxPhoneRingButton(coordinator),
    ]
    for rep in coordinator.data.repeaters:
        if isinstance(rep, dict) and rep.get("id") is not None:
            entities.append(FreeboxRepeaterRebootButton(coordinator, rep))
    for player in coordinator.data.players:
        if isinstance(player, dict) and player.get("id") is not None:
            entities.append(FreeboxPlayerRebootButton(coordinator, player))
    for vm in coordinator.data.vms:
        if isinstance(vm, dict) and vm.get("id") is not None:
            entities.append(FreeboxVmRestartButton(coordinator, vm))
    async_add_entities(entities)


class FreeboxRebootButton(CoordinatorEntity[FreeboxHomeCoordinator], ButtonEntity):
    """Button to reboot the Freebox Server via POST system/reboot/."""

    _attr_has_entity_name = True
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_name = "03 · Système · Redémarrer Freebox"
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator: FreeboxHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.host}_reboot"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    async def async_press(self) -> None:
        await self.coordinator.client.async_reboot()


class FreeboxWpsButton(CoordinatorEntity[FreeboxHomeCoordinator], ButtonEntity):
    """Button to start a Wi-Fi WPS pairing session."""

    _attr_has_entity_name = True
    _attr_name = "02 · Wi-Fi · Démarrer WPS"
    _attr_icon = "mdi:wifi-sync"

    def __init__(self, coordinator: FreeboxHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.host}_wps_start"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    async def async_press(self) -> None:
        await self.coordinator.client.async_start_wps()


class FreeboxMarkCallsReadButton(CoordinatorEntity[FreeboxHomeCoordinator], ButtonEntity):
    """Button to mark all missed Freebox phone calls as read."""

    _attr_has_entity_name = True
    _attr_name = "04 · Téléphonie · Marquer appels lus"
    _attr_icon = "mdi:phone-check"

    def __init__(self, coordinator: FreeboxHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.host}_mark_calls_read"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    async def async_press(self) -> None:
        await self.coordinator.client.async_mark_calls_read()
        await self.coordinator.async_request_refresh()


class FreeboxRepeaterRebootButton(CoordinatorEntity[FreeboxHomeCoordinator], ButtonEntity):
    """Button to reboot a paired Wi-Fi repeater."""

    _attr_has_entity_name = True
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, coordinator: FreeboxHomeCoordinator, rep: dict) -> None:
        super().__init__(coordinator)
        self._rep_id = str(rep["id"])
        self._attr_unique_id = f"repeater_{self._rep_id}_reboot"
        self._attr_name = f"02 · Wi-Fi · Redémarrer Répéteur {rep.get('name') or self._rep_id}"
        self._attr_icon = "mdi:restart"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    async def async_press(self) -> None:
        await self.coordinator.client.async_reboot_repeater(self._rep_id)


class FreeboxPlayerRebootButton(CoordinatorEntity[FreeboxHomeCoordinator], ButtonEntity):
    """Button to reboot a Freebox TV Player."""

    _attr_has_entity_name = True
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, coordinator: FreeboxHomeCoordinator, player: dict) -> None:
        super().__init__(coordinator)
        self._player_id = str(player["id"])
        self._attr_unique_id = f"player_{self._player_id}_reboot"
        model_label, _ = resolve_player_model(player)
        self._attr_name = f"07 · TV / Players · Redémarrer {model_label}"
        self._attr_icon = "mdi:television-box"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    async def async_press(self) -> None:
        await self.coordinator.client.async_reboot_player(self._player_id)


class FreeboxPhoneRingButton(CoordinatorEntity[FreeboxHomeCoordinator], ButtonEntity):
    """Button to trigger a test ring on the Freebox fixed phone / DECT handsets."""

    _attr_has_entity_name = True
    _attr_name = "04 · Téléphonie · Faire sonner le téléphone"
    _attr_icon = "mdi:phone-ring"

    def __init__(self, coordinator: FreeboxHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.host}_phone_ring"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    async def async_press(self) -> None:
        await self.coordinator.client.async_ring_phone()


class FreeboxVmRestartButton(CoordinatorEntity[FreeboxHomeCoordinator], ButtonEntity):
    """Button to restart a Freebox OS Virtual Machine."""

    _attr_has_entity_name = True
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator: FreeboxHomeCoordinator, vm: dict) -> None:
        super().__init__(coordinator)
        self._vm_id = str(vm["id"])
        name = str(vm.get("name") or f"VM {self._vm_id}")
        self._attr_unique_id = f"vm_{self._vm_id}_restart"
        self._attr_name = f"08 · Machines Virtuelles · Redémarrer VM {name}"
        self._attr_device_info = box_device_info(
            coordinator.client.host, coordinator.data.system
        )

    async def async_press(self) -> None:
        await self.coordinator.client.async_restart_vm(self._vm_id)
