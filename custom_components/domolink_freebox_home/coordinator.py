"""DataUpdateCoordinator for DomoLink Freebox Home."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FreeboxAuthError, FreeboxOsClient, FreeboxOsError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class FreeboxHomeData:
    """Aggregated Freebox OS & Home snapshot."""

    system: dict[str, Any] = field(default_factory=dict)
    connection: dict[str, Any] = field(default_factory=dict)
    lte: dict[str, Any] = field(default_factory=dict)
    repeaters: list[dict[str, Any]] = field(default_factory=list)
    nodes: dict[int, dict[str, Any]] = field(default_factory=dict)
    cameras: list[dict[str, Any]] = field(default_factory=list)
    wifi_config: dict[str, Any] = field(default_factory=dict)
    wifi_bss: list[dict[str, Any]] = field(default_factory=list)
    lan_hosts: list[dict[str, Any]] = field(default_factory=list)
    profiles: list[dict[str, Any]] = field(default_factory=list)
    network_controls: list[dict[str, Any]] = field(default_factory=list)
    partitions: list[dict[str, Any]] = field(default_factory=list)
    call_logs: list[dict[str, Any]] = field(default_factory=list)
    voicemails: list[dict[str, Any]] = field(default_factory=list)
    vpn_servers: list[dict[str, Any]] = field(default_factory=list)
    vpn_connections: list[dict[str, Any]] = field(default_factory=list)
    players: list[dict[str, Any]] = field(default_factory=list)
    lcd: dict[str, Any] = field(default_factory=dict)
    update_status: dict[str, Any] = field(default_factory=dict)


class FreeboxHomeCoordinator(DataUpdateCoordinator[FreeboxHomeData]):
    """Coordinator polling Freebox OS, Home nodes, and Cameras."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: FreeboxOsClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{client.host}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self.entry = entry

    async def _async_update_data(self) -> FreeboxHomeData:
        try:
            # First authenticate & fetch required core endpoints so session_token is guaranteed valid
            system = await self.client.async_get_system_config()
            connection = await self.client.async_get_connection_status()

            (
                lte,
                repeaters,
                nodes_list,
                cameras,
                wifi_config,
                wifi_bss,
                lan_hosts,
                profiles,
                network_controls,
                partitions,
                call_logs,
                voicemails,
                vpn_servers,
                vpn_connections,
                players,
                lcd,
                update_status,
            ) = await asyncio.gather(
                self.client.async_get_lte_aggregation(),
                self.client.async_get_repeaters(),
                self.client.async_get_home_nodes(),
                self.client.async_get_cameras(),
                self.client.async_get_wifi_config(),
                self.client.async_get_wifi_bss(),
                self.client.async_get_lan_hosts(),
                self.client.async_get_profiles(),
                self.client.async_get_network_controls(),
                self.client.async_get_storage_partitions(),
                self.client.async_get_call_logs(),
                self.client.async_get_voicemails(),
                self.client.async_get_vpn_servers(),
                self.client.async_get_vpn_connections(),
                self.client.async_get_players(),
                self.client.async_get_lcd_config(),
                self.client.async_get_update_status(),
            )
            nodes_map: dict[int, dict[str, Any]] = {}
            for node in nodes_list:
                if isinstance(node, dict) and node.get("id") is not None:
                    nodes_map[int(node["id"])] = node

            _LOGGER.debug(
                "Freebox updated (%s %s): nodes=%d cameras=%d repeaters=%d lan=%d",
                system.get("board_name", "unknown"),
                self.client.api_version,
                len(nodes_map),
                len(cameras),
                len(repeaters),
                len(lan_hosts),
            )
            return FreeboxHomeData(
                system=system,
                connection=connection,
                lte=lte,
                repeaters=repeaters,
                nodes=nodes_map,
                cameras=cameras,
                wifi_config=wifi_config,
                wifi_bss=wifi_bss,
                lan_hosts=lan_hosts,
                profiles=profiles,
                network_controls=network_controls,
                partitions=partitions,
                call_logs=call_logs,
                voicemails=voicemails,
                vpn_servers=vpn_servers,
                vpn_connections=vpn_connections,
                players=players,
                lcd=lcd,
                update_status=update_status,
            )
        except FreeboxAuthError as err:
            raise ConfigEntryAuthFailed(f"Freebox auth error: {err}") from err
        except FreeboxOsError as err:
            raise UpdateFailed(f"Freebox update failed: {err}") from err
