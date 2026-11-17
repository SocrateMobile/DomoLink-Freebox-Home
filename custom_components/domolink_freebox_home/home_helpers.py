"""Shared helpers for mapping Freebox Home nodes and endpoints to HA entities."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MANUFACTURER


def node_device_info(node: dict[str, Any]) -> DeviceInfo:
    """Build Home Assistant DeviceInfo from a Freebox HomeNode dict."""
    node_id = str(node["id"])
    return DeviceInfo(
        identifiers={(DOMAIN, f"node_{node_id}")},
        name=str(node.get("label") or f"Freebox Node {node_id}"),
        manufacturer=MANUFACTURER,
        model=str(node.get("category") or node.get("type", {}).get("label") or "Freebox Home"),
    )


def box_device_info(host: str, system: dict[str, Any]) -> DeviceInfo:
    """Build DeviceInfo for the Freebox Server hub."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"box_{system.get('mac') or host}")},
        name=str(system.get("box_flavor") or system.get("board_name") or "Freebox Server"),
        manufacturer=MANUFACTURER,
        model=str(system.get("board_name") or "Freebox"),
        sw_version=str(system.get("firmware_version") or ""),
    )


def find_endpoint(
    node: dict[str, Any],
    *,
    name: str | None = None,
    ep_type: str | None = None,
    category: str | None = None,
) -> dict[str, Any] | None:
    """Find the first matching endpoint inside a Freebox HomeNode."""
    for ep in node.get("show_endpoints") or node.get("endpoints") or []:
        if not isinstance(ep, dict):
            continue
        if name is not None and ep.get("name") != name:
            continue
        if ep_type is not None and ep.get("ep_type") != ep_type:
            continue
        if category is not None and ep.get("category") != category:
            continue
        return ep
    return None
