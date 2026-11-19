"""Shared helpers for mapping Freebox Home nodes, LAN hosts, and box metadata."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MANUFACTURER

HOST_TYPE_ICONS: dict[str, str] = {
    "smartphone": "mdi:cellphone",
    "tablet": "mdi:tablet",
    "laptop": "mdi:laptop",
    "workstation": "mdi:desktop-tower-monitor",
    "desktop": "mdi:desktop-tower-monitor",
    "tv": "mdi:television",
    "television": "mdi:television",
    "multimedia_device": "mdi:television-box",
    "set_top_box": "mdi:set-top-box",
    "printer": "mdi:printer",
    "nas": "mdi:nas",
    "storage": "mdi:harddisk",
    "ip_camera": "mdi:cctv",
    "camera": "mdi:cctv",
    "game_console": "mdi:gamepad-variant",
    "watch": "mdi:watch",
    "networking_device": "mdi:router-network",
    "repeater": "mdi:wifi-star",
    "router": "mdi:router-wireless",
    "car": "mdi:car-connected",
    "iot": "mdi:home-automation",
    "smart_home": "mdi:home-automation",
    "lighting": "mdi:lightbulb",
    "plug": "mdi:power-plug",
    "speaker": "mdi:speaker-wireless",
    "audio": "mdi:speaker-wireless",
}


def host_type_icon(host_type: str | None, active: bool) -> str:
    """Return a representative MDI icon for a Freebox LAN host_type."""
    key = str(host_type or "").strip().lower()
    if key in HOST_TYPE_ICONS:
        return HOST_TYPE_ICONS[key]
    return "mdi:lan-connect" if active else "mdi:lan-disconnect"


def node_device_info(node: dict[str, Any]) -> DeviceInfo:
    """Build Home Assistant DeviceInfo from a Freebox HomeNode dict."""
    node_id = str(node["id"])
    raw_label = str(node.get("label") or f"Module {node_id}")
    name = raw_label if raw_label.lower().startswith("freebox") else f"Freebox · {raw_label}"
    return DeviceInfo(
        identifiers={(DOMAIN, f"node_{node_id}")},
        name=name,
        manufacturer=MANUFACTURER,
        model=str(node.get("category") or node.get("type", {}).get("label") or "Freebox Home"),
    )


def box_device_info(host: str, system: dict[str, Any]) -> DeviceInfo:
    """Build DeviceInfo for the Freebox Server hub (always prefixed with Freebox)."""
    model_info = system.get("model_info") if isinstance(system.get("model_info"), dict) else {}
    pretty = str(model_info.get("pretty_name") or "").strip()
    board = str(system.get("board_name") or "").strip()
    if pretty:
        name = pretty if pretty.lower().startswith("freebox") else f"Freebox {pretty}"
    elif board:
        name = f"Freebox ({board})"
    else:
        name = "Freebox Server"
    return DeviceInfo(
        identifiers={(DOMAIN, f"box_{system.get('mac') or host}")},
        name=name,
        manufacturer=MANUFACTURER,
        model=pretty or board or "Freebox Server",
        sw_version=str(system.get("firmware_version") or ""),
    )


def wifi_clients_device_info(host: str, system: dict[str, Any]) -> DeviceInfo:
    """Build DeviceInfo for the dedicated 'Wi-Fi' sub-device grouping LAN/Wi-Fi clients."""
    box_id = system.get("mac") or host
    return DeviceInfo(
        identifiers={(DOMAIN, f"wifi_clients_{box_id}")},
        name="Wi-Fi",
        manufacturer=MANUFACTURER,
        model="Périphériques Wi-Fi / Réseau",
        via_device=(DOMAIN, f"box_{box_id}"),
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
