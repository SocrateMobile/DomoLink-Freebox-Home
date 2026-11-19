"""Shared helpers for mapping Freebox Home nodes, LAN hosts, and box metadata."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MANUFACTURER

_REV_RE = re.compile(r"\((r\d+)\)", re.IGNORECASE)
_VER_RE = re.compile(r"\b(v\d+)\b", re.IGNORECASE)


def resolve_freebox_model(system: dict[str, Any]) -> tuple[str, str, str]:
    """Resolve (display_name, commercial_name, asset_filename) from Freebox OS system payload.

    Maps all official Freebox hardware signatures (model_info.name, board_name,
    box_flavor, pretty_name) to their commercial names (Ultra, Pop, Delta,
    Révolution, Mini 4K, One, Crystal, 5G, 4G+).
    """
    model_info = system.get("model_info") if isinstance(system.get("model_info"), dict) else {}
    pretty = str(model_info.get("pretty_name") or "").strip()
    model_name = str(model_info.get("name") or "").strip().lower()
    board = str(system.get("board_name") or "").strip().lower()
    flavor = str(system.get("box_flavor") or "").strip().lower()
    sig = f"{model_name} {board} {pretty.lower()} {flavor}"

    is_light = (
        flavor in ("light", "essentiel")
        or "/light" in model_name
        or "essentiel" in sig
        or "delta s" in sig
        or "pop s" in sig
    )

    # Extract version (e.g. v9) and hardware revision (e.g. (r1))
    ver_match = _VER_RE.search(pretty)
    rev_match = _REV_RE.search(pretty)
    if not rev_match:
        rev_sig = re.search(r"-(r\d+)\b", model_name)
        rev_str = f"({rev_sig.group(1).lower()})" if rev_sig else ""
    else:
        rev_str = f"({rev_match.group(1).lower()})"

    commercial = ""
    default_ver = ""
    asset = "freebox_ultra.png"

    if any(k in sig for k in ("fbxgw9", "v9", "ultra")):
        commercial = "Freebox Ultra Essentiel" if is_light else "Freebox Ultra"
        default_ver = "v9"
        asset = "freebox_ultra.png"
    elif any(k in sig for k in ("fbxgw8", "v8", "pop")):
        commercial = "Freebox Pop S" if is_light else "Freebox Pop"
        default_ver = "v8"
        asset = "freebox_pop.png"
    elif any(k in sig for k in ("fbxgw7", "v7", "delta")):
        commercial = "Freebox Delta S" if is_light else "Freebox Delta"
        default_ver = "v7"
        asset = "freebox_delta.png"
    elif "/one" in model_name or flavor == "one" or "freebox one" in pretty.lower():
        commercial = "Freebox One"
        asset = "freebox_mini_4k.png"
    elif "/mini" in model_name or flavor == "mini" or "mini" in pretty.lower():
        commercial = "Freebox Mini 4K"
        asset = "freebox_mini_4k.png"
    elif any(k in sig for k in ("fbx5g", "box 5g", "freebox 5g")):
        commercial = "Freebox 5G"
        asset = "freebox_5g.png"
    elif any(k in sig for k in ("fbx4g", "box 4g", "freebox 4g")):
        commercial = "Freebox 4G+"
        asset = "freebox_5g.png"
    elif any(k in sig for k in ("crystal", "fbxgw5", "v5")):
        commercial = "Freebox Crystal"
        asset = "freebox_mini_4k.png"
    elif any(
        k in sig
        for k in ("fbxgw-r1", "fbxgw-r2", "fbxgw2r", "fbxgw1r", "v6", "revolution", "révolution", "freebox server")
    ):
        commercial = "Freebox Révolution"
        default_ver = "v6"
        asset = "freebox_revolution.png"

    if commercial:
        ver_str = ver_match.group(1).lower() if ver_match else default_ver
        parts = [commercial]
        if ver_str and ver_str not in commercial.lower():
            parts.append(ver_str)
        if rev_str and rev_str not in commercial.lower():
            parts.append(rev_str)
        return " ".join(parts), commercial, asset

    if pretty:
        display = pretty if pretty.lower().startswith("freebox") else f"Freebox {pretty}"
        return display, display, asset
    if board:
        return f"Freebox ({board})", "Freebox Server", asset
    return "Freebox Server", "Freebox Server", asset

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
    """Build DeviceInfo for the Freebox Server hub with commercial model name."""
    display_name, _commercial, _asset = resolve_freebox_model(system)
    return DeviceInfo(
        identifiers={(DOMAIN, f"box_{system.get('mac') or host}")},
        name=display_name,
        manufacturer=MANUFACTURER,
        model=display_name,
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
