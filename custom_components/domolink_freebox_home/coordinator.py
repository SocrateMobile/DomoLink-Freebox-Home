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
            system, connection, lte, repeaters, nodes_list, cameras = await asyncio.gather(
                self.client.async_get_system_config(),
                self.client.async_get_connection_status(),
                self.client.async_get_lte_aggregation(),
                self.client.async_get_repeaters(),
                self.client.async_get_home_nodes(),
                self.client.async_get_cameras(),
            )
            nodes_map: dict[int, dict[str, Any]] = {}
            for node in nodes_list:
                if isinstance(node, dict) and node.get("id") is not None:
                    nodes_map[int(node["id"])] = node

            _LOGGER.debug(
                "Freebox updated (%s %s): nodes=%d cameras=%d repeaters=%d",
                system.get("board_name", "unknown"),
                self.client.api_version,
                len(nodes_map),
                len(cameras),
                len(repeaters),
            )
            return FreeboxHomeData(
                system=system,
                connection=connection,
                lte=lte,
                repeaters=repeaters,
                nodes=nodes_map,
                cameras=cameras,
            )
        except FreeboxAuthError as err:
            raise ConfigEntryAuthFailed(f"Freebox auth error: {err}") from err
        except FreeboxOsError as err:
            raise UpdateFailed(f"Freebox update failed: {err}") from err
