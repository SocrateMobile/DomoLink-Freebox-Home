"""Unit tests for DomoLink Freebox Home v2.0.0 features."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import sys
import types

import pytest

# Ensure stubs exist if run standalone
ha_pkg = types.ModuleType("homeassistant")
ha_const = types.ModuleType("homeassistant.const")
ha_const.Platform = types.SimpleNamespace(
    SENSOR="sensor",
    BINARY_SENSOR="binary_sensor",
    SWITCH="switch",
    COVER="cover",
    LIGHT="light",
    ALARM_CONTROL_PANEL="alarm_control_panel",
    CAMERA="camera",
    IMAGE="image",
    BUTTON="button",
    DEVICE_TRACKER="device_tracker",
    NUMBER="number",
    SELECT="select",
    UPDATE="update",
)
ha_const.CONF_HOST = "host"
ha_const.CONF_PORT = "port"
ha_core = types.ModuleType("homeassistant.core")
ha_core.HomeAssistant = object
ha_core.ServiceCall = object
ha_ce = types.ModuleType("homeassistant.config_entries")
ha_ce.ConfigEntry = object
ha_exc = types.ModuleType("homeassistant.exceptions")
ha_exc.ConfigEntryAuthFailed = type("ConfigEntryAuthFailed", (Exception,), {})
ha_helpers = types.ModuleType("homeassistant.helpers")
ha_aio = types.ModuleType("homeassistant.helpers.aiohttp_client")
ha_aio.async_get_clientsession = lambda hass: None
ha_dr = types.ModuleType("homeassistant.helpers.device_registry")
ha_dr.DeviceInfo = dict
ha_dr.CONNECTION_NETWORK_MAC = "mac"
ha_uc = types.ModuleType("homeassistant.helpers.update_coordinator")
ha_uc.DataUpdateCoordinator = type("DataUpdateCoordinator", (), {"__class_getitem__": classmethod(lambda cls, item: cls)})
ha_uc.UpdateFailed = type("UpdateFailed", (Exception,), {})
ha_comp = types.ModuleType("homeassistant.components")
ha_dt = types.ModuleType("homeassistant.components.device_tracker")
ha_dt.SourceType = types.SimpleNamespace(ROUTER="router")
ha_dt.ScannerEntity = object
ha_dt_ce = types.ModuleType("homeassistant.components.device_tracker.config_entry")
ha_dt_ce.ScannerEntity = object
ha_ep = types.ModuleType("homeassistant.helpers.entity_platform")
ha_ep.AddEntitiesCallback = object

for name, mod in [
    ("homeassistant", ha_pkg),
    ("homeassistant.const", ha_const),
    ("homeassistant.core", ha_core),
    ("homeassistant.config_entries", ha_ce),
    ("homeassistant.exceptions", ha_exc),
    ("homeassistant.helpers", ha_helpers),
    ("homeassistant.helpers.aiohttp_client", ha_aio),
    ("homeassistant.helpers.device_registry", ha_dr),
    ("homeassistant.helpers.update_coordinator", ha_uc),
    ("homeassistant.helpers.entity_platform", ha_ep),
    ("homeassistant.components", ha_comp),
    ("homeassistant.components.device_tracker", ha_dt),
    ("homeassistant.components.device_tracker.config_entry", ha_dt_ce),
]:
    sys.modules.setdefault(name, mod)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from custom_components.domolink_freebox_home.api import FreeboxOsClient  # noqa: E402
from custom_components.domolink_freebox_home.device_tracker import (  # noqa: E402
    extract_mac,
    resolve_host_name,
)


class FakeResponse:
    def __init__(self, json_data: dict, status: int = 200) -> None:
        self._json = json_data
        self.status = status

    async def json(self) -> dict:
        return self._json


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str, dict]] = []

    def request(self, method: str, url: str, **kwargs):
        self.calls.append((method, url, kwargs))
        resp = self._responses.pop(0)

        @asynccontextmanager
        async def _cm():
            yield resp

        return _cm()


def test_wifi_bss_and_wps_calls():
    session = FakeSession([
        FakeResponse({"success": True, "result": {"id": "bss_1", "config": {"enabled": False}}}),
        FakeResponse({"success": True, "result": {}}),
    ])
    client = FreeboxOsClient(session, host="mafreebox.freebox.fr", app_token="tok")
    client.session_token = "sess"

    res = asyncio.run(client.async_set_wifi_bss_enabled("bss_1", False))
    assert res["id"] == "bss_1"
    assert session.calls[0][0] == "PUT"
    assert session.calls[0][1].endswith("/wifi/bss/bss_1")
    assert session.calls[0][2]["json"] == {"config": {"enabled": False}}

    assert asyncio.run(client.async_start_wps()) is True
    assert session.calls[1][0] == "POST"
    assert session.calls[1][1].endswith("/wifi/wps/start/")


def test_lan_hosts_and_wol_payload():
    session = FakeSession([
        FakeResponse({"success": True, "result": [{"id": "ether-aa:bb:cc:dd:ee:ff", "l2ident": {"type": "mac_address", "id": "AA:BB:CC:DD:EE:FF"}, "active": True}]}),
        FakeResponse({"success": True, "result": {}}),
    ])
    client = FreeboxOsClient(session, host="mafreebox.freebox.fr", app_token="tok")
    client.session_token = "sess"

    hosts = asyncio.run(client.async_get_lan_hosts())
    assert len(hosts) == 1
    assert extract_mac(hosts[0]) == "aa:bb:cc:dd:ee:ff"

    assert asyncio.run(client.async_wake_on_lan("AA:BB:CC:DD:EE:FF")) is True
    assert session.calls[1][0] == "POST"
    assert session.calls[1][1].endswith("/lan/wol/pub/")
    assert session.calls[1][2]["json"] == {"mac": "AA:BB:CC:DD:EE:FF"}


def test_lcd_and_vpn_optional_degradation():
    err_404 = {"success": False, "error_code": "invalid_request", "msg": "Requête invalide (404)"}
    session = FakeSession([
        FakeResponse(err_404, status=404),
        FakeResponse(err_404, status=404),
        FakeResponse({"success": True, "result": {"brightness": 60}}),
    ])
    client = FreeboxOsClient(session, host="mafreebox.freebox.fr", app_token="tok")
    client.session_token = "sess"

    assert asyncio.run(client.async_get_lcd_config()) == {}
    assert asyncio.run(client.async_get_vpn_servers()) == []

    res = asyncio.run(client.async_set_lcd_brightness(60))
    assert res["brightness"] == 60
    assert session.calls[2][2]["json"] == {"brightness": 60}


def test_optional_auth_required_does_not_wipe_session_token():
    session = FakeSession([
        FakeResponse({"success": False, "error_code": "auth_required", "msg": "Missing right"}),
        FakeResponse({"success": False, "error_code": "access_denied", "msg": "Denied"}),
        FakeResponse({"success": False, "error_code": "ratelimited", "msg": "Too many requests"}),
    ])
    client = FreeboxOsClient(session, host="mafreebox.freebox.fr", app_token="tok")
    client.session_token = "active-session"

    assert asyncio.run(client.async_get_call_logs()) == []
    assert asyncio.run(client.async_get_vpn_servers()) == []
    assert asyncio.run(client.async_get_players()) == []
    assert client.session_token == "active-session"


def test_resolve_host_name_prefers_friendly_name_over_mac():
    mac = "aa:bb:cc:dd:ee:ff"
    assert resolve_host_name({"primary_name": "iPhone Salon"}, mac) == "iPhone Salon"
    assert (
        resolve_host_name(
            {"primary_name": "AA:BB:CC:DD:EE:FF", "names": [{"name": "MacBook-Pro"}]},
            mac,
        )
        == "MacBook-Pro"
    )
    assert (
        resolve_host_name(
            {"primary_name": "", "vendor_name": "Apple, Inc."},
            mac,
        )
        == "Apple, Inc. (EE:FF)"
    )
    assert resolve_host_name({}, mac) == "AA:BB:CC:DD:EE:FF"


def test_box_device_info_uses_pretty_name():
    from custom_components.domolink_freebox_home.home_helpers import (
        box_device_info,
        resolve_freebox_model,
    )

    info = box_device_info(
        "mafreebox.freebox.fr",
        {
            "mac": "AA:BB:CC:DD:EE:FF",
            "box_flavor": "full",
            "board_name": "fbxgw9r",
            "firmware_version": "4.8.15",
            "model_info": {"name": "fbxgw9-r1/full", "pretty_name": "Freebox v9 (r1)"},
        },
    )
    assert info["name"] == "Freebox Ultra v9 (r1)"
    assert info["model"] == "Freebox Ultra v9 (r1)"
    assert info["sw_version"] == "4.8.15"

    cases = [
        ({"board_name": "fbxgw9r", "box_flavor": "full", "model_info": {"name": "fbxgw9-r1/full", "pretty_name": "Freebox v9 (r1)"}}, "Freebox Ultra v9 (r1)", "freebox_ultra.png"),
        ({"board_name": "fbxgw9r", "box_flavor": "light", "model_info": {"name": "fbxgw9-r1/light", "pretty_name": "Freebox v9 (r1)"}}, "Freebox Ultra Essentiel v9 (r1)", "freebox_ultra.png"),
        ({"board_name": "fbxgw8r", "box_flavor": "full", "model_info": {"name": "fbxgw8-r1/full", "pretty_name": "Freebox v8 (r1)"}}, "Freebox Pop v8 (r1)", "freebox_pop.png"),
        ({"board_name": "fbxgw8r", "box_flavor": "light", "model_info": {"name": "fbxgw8-r1/light", "pretty_name": "Freebox v8 (r1)"}}, "Freebox Pop S v8 (r1)", "freebox_pop.png"),
        ({"board_name": "fbxgw7r", "box_flavor": "full", "model_info": {"name": "fbxgw7-r1/full", "pretty_name": "Freebox v7 (r1)"}}, "Freebox Delta v7 (r1)", "freebox_delta.png"),
        ({"board_name": "fbxgw7r", "box_flavor": "light", "model_info": {"name": "fbxgw7-r1/light", "pretty_name": "Freebox v7 (r1)"}}, "Freebox Delta S v7 (r1)", "freebox_delta.png"),
        ({"board_name": "fbxgw2r", "box_flavor": "full", "model_info": {"name": "fbxgw-r2/full", "pretty_name": "Freebox Server (r2)"}}, "Freebox Révolution v6 (r2)", "freebox_revolution.png"),
        ({"board_name": "fbxgw1r", "box_flavor": "mini", "model_info": {"name": "fbxgw-r1/mini", "pretty_name": "Freebox Mini (r1)"}}, "Freebox Mini 4K (r1)", "freebox_mini_4k.png"),
        ({"board_name": "fbxgw1r", "box_flavor": "one", "model_info": {"name": "fbxgw-r1/one", "pretty_name": "Freebox One (r1)"}}, "Freebox One (r1)", "freebox_mini_4k.png"),
        ({"board_name": "fbxgw5", "model_info": {"name": "freebox_crystal", "pretty_name": "Freebox Crystal"}}, "Freebox Crystal", "freebox_mini_4k.png"),
        ({"board_name": "fbx5g", "model_info": {"name": "fbx5g", "pretty_name": "Box 5G"}}, "Freebox 5G", "freebox_5g.png"),
        ({"board_name": "fbx4g", "model_info": {"name": "fbx4g", "pretty_name": "Box 4G+"}}, "Freebox 4G+", "freebox_5g.png"),
        ({"board_name": "fbxpro", "box_flavor": "pro", "model_info": {"name": "fbxgwpro-r1/pro", "pretty_name": "Freebox Pro (r1)"}}, "Freebox Pro (r1)", "freebox_pro.png"),
        ({"board_name": "fbxgwpro", "box_flavor": "pro", "model_info": {"name": "fbxgwpro-r2/pro", "pretty_name": "Freebox Pro (r2)", "wifi_type": "2d4_5g_6g"}}, "Freebox Pro Wi-Fi 7 (r2)", "freebox_pro.png"),
    ]
    assets_dir = ROOT / "custom_components" / "domolink_freebox_home" / "assets"
    for payload, expected_name, expected_asset in cases:
        display, _commercial, asset = resolve_freebox_model(payload)
        assert display == expected_name
        assert asset == expected_asset
        assert (assets_dir / asset).is_file()
    assert (assets_dir / "freebox_repeater.png").is_file()
    assert (assets_dir / "freebox_repeater_wifi5.png").is_file()
    assert (assets_dir / "freebox_repeater_wifi7.png").is_file()

    from custom_components.domolink_freebox_home.home_helpers import resolve_repeater_model

    assert resolve_repeater_model({"model": "F-RPQ2A"}) == ("Répéteur Wi-Fi 7", "freebox_repeater_wifi7.png")
    assert resolve_repeater_model({"model": "F-RPQ1A"}) == ("Répéteur Wi-Fi 5 (Pop)", "freebox_repeater_wifi5.png")
    assert resolve_repeater_model({"name": "Répéteur Salon", "wifi_type": "2d4_5g_6g"}) == ("Répéteur Wi-Fi 7", "freebox_repeater_wifi7.png")
    assert resolve_repeater_model(None, {"board_name": "fbxgw9r"}) == ("Répéteur Wi-Fi 7", "freebox_repeater_wifi7.png")
    assert resolve_repeater_model(None, {"board_name": "fbxgw8r"}) == ("Répéteur Wi-Fi 5 (Pop)", "freebox_repeater_wifi5.png")

    from custom_components.domolink_freebox_home.home_helpers import resolve_player_model

    player_cases = [
        ({"device_model": "fbx8am"}, "Player TV Free 4K (Pop)", "freebox_player_pop.png"),
        ({"device_model": "fbx7hd-delta"}, "Player Free Devialet (Delta)", "freebox_player_devialet.png"),
        ({"device_model": "fbx7hd_one"}, "Player Freebox One", "freebox_mini_4k.png"),
        ({"device_model": "fbx6hd"}, "Player Freebox Révolution", "freebox_player_revolution.png"),
        ({"device_model": "fbx6lcv2"}, "Player Freebox Mini 4K", "freebox_mini_4k.png"),
        ({"device_model": "appletv"}, "Apple TV 4K (Free)", "freebox_player_appletv.png"),
    ]
    for p_payload, exp_label, exp_asset in player_cases:
        assert resolve_player_model(p_payload) == (exp_label, exp_asset)
        assert (assets_dir / exp_asset).is_file()


def test_lan_status_dots_icons_and_sorting():
    from custom_components.domolink_freebox_home.device_tracker import (
        FreeboxLanDeviceTracker,
        format_lan_device_label,
    )
    from custom_components.domolink_freebox_home.home_helpers import (
        host_type_icon,
        wifi_clients_device_info,
    )

    assert FreeboxLanDeviceTracker._attr_entity_registry_enabled_default is True
    assert format_lan_device_label("iPhone", True) == "🟢 iPhone"
    assert format_lan_device_label("iPhone", True, "aa:bb:cc:dd:ee:ff") == "🟢 iPhone (AA:BB:CC:DD:EE:FF)"
    assert format_lan_device_label("MacBook", False) == "🟠 MacBook"
    assert "Freebox Ultra" < format_lan_device_label("AAA", True)
    assert host_type_icon("smartphone", True) == "mdi:cellphone"
    assert host_type_icon("workstation", True) == "mdi:desktop-tower-monitor"
    assert host_type_icon("unknown_xyz", True) == "mdi:lan-connect"
    assert host_type_icon("unknown_xyz", False) == "mdi:lan-disconnect"

    wifi_dev = wifi_clients_device_info("mafreebox.freebox.fr", {"mac": "AA:BB:CC:DD:EE:FF"})
    assert wifi_dev["name"] == "Wi-Fi"


def test_v26_ftth_freeplug_vm_seedbox_phone_pvr_calls():
    session = FakeSession([
        FakeResponse({"success": True, "result": {"link": True, "sfp_pwr_rx": -1850, "sfp_pwr_tx": 230}}),
        FakeResponse({"success": True, "result": [{"id": "fp1", "members": [{"id": "AA:BB", "has_network": True}]}]}),
        FakeResponse({"success": True, "result": [{"id": 1, "name": "Debian", "status": "running"}]}),
        FakeResponse({"success": True, "result": {}}),
        FakeResponse({"success": True, "result": {"nb_tasks_active": 2, "rx_rate": 1250000, "tx_rate": 250000}}),
        FakeResponse({"success": True, "result": [{"id": 1, "type": "dect", "name": "Salon"}]}),
        FakeResponse({"success": True, "result": {}}),
        FakeResponse({"success": True, "result": [{"id": 10}]}),
        FakeResponse({"success": True, "result": [{"id": 11}, {"id": 12}]}),
    ])
    client = FreeboxOsClient(session, host="mafreebox.freebox.fr", app_token="tok")
    client.session_token = "sess"

    ftth = asyncio.run(client.async_get_ftth())
    assert ftth["link"] is True and ftth["sfp_pwr_rx"] == -1850
    fps = asyncio.run(client.async_get_freeplugs())
    assert len(fps[0]["members"]) == 1
    vms = asyncio.run(client.async_get_vms())
    assert vms[0]["name"] == "Debian"
    assert asyncio.run(client.async_restart_vm(1)) is True
    dl = asyncio.run(client.async_get_download_stats())
    assert dl["nb_tasks_active"] == 2
    phones = asyncio.run(client.async_get_phones())
    assert len(phones) == 1
    assert asyncio.run(client.async_ring_phone()) is True
    assert len(asyncio.run(client.async_get_pvr_programmed())) == 1
    assert len(asyncio.run(client.async_get_pvr_finished())) == 2


def test_classify_lan_host_brands_and_models():
    from custom_components.domolink_freebox_home.device_signatures import classify_lan_host

    samples = [
        ({"primary_name": "iPhone-de-JF", "vendor_name": "Apple, Inc."}, "Apple", "mdi:cellphone"),
        ({"primary_name": "MacBook-Pro", "vendor_name": "Apple, Inc."}, "Apple", "mdi:laptop"),
        ({"primary_name": "[TV] Samsung QLED", "vendor_name": "Samsung Electronics"}, "Samsung", "mdi:television"),
        ({"primary_name": "Roborock-S8", "vendor_name": "Xiaomi"}, "Aspirateur Robot", "mdi:robot-vacuum"),
        ({"primary_name": "Denon-AVR-X2800H"}, "Denon", "mdi:amplifier"),
        ({"primary_name": "Onkyo-TX-NR6100"}, "Onkyo", "mdi:amplifier"),
        ({"primary_name": "Sony-Bravia-XR"}, "Sony", "mdi:television"),
        ({"primary_name": "PS5-Salon"}, "Sony", "mdi:sony-playstation"),
        ({"primary_name": "LG-OLED65C3"}, "LG", "mdi:television"),
        ({"primary_name": "Hisense-VIDAA"}, "Hisense", "mdi:television"),
        ({"primary_name": "TCL-65C845"}, "TCL", "mdi:television"),
        ({"primary_name": "EssentielB-TV"}, "Essentiel B", "mdi:television"),
        ({"primary_name": "Prise-Salon", "vendor_name": "Tuya Smart"}, "Tuya", "mdi:home-automation"),
        ({"primary_name": "Sonoff-NSPanel"}, "Sonoff", "mdi:light-switch"),
        ({"primary_name": "Reolink-RLC-811A"}, "Reolink", "mdi:cctv"),
        ({"primary_name": "esphome-salon", "vendor_name": "Espressif"}, "ESPHome", "mdi:chip"),
        ({"primary_name": "Arlo-Base-VMB4540"}, "Arlo", "mdi:cctv"),
        ({"primary_name": "Ezviz-C8C"}, "Ezviz", "mdi:cctv"),
        ({"primary_name": "Asustor-AS5402T"}, "Asustor", "mdi:nas"),
        ({"primary_name": "Synology-DS923"}, "Synology", "mdi:nas"),
        ({"primary_name": "TrueNAS-Scale"}, "TrueNAS", "mdi:nas"),
        ({"primary_name": "Google-TV-Streamer"}, "Google", "mdi:television-box"),
        ({"primary_name": "Chromecast-Salon"}, "Google", "mdi:television-box"),
        ({"primary_name": "Xiaomi-TV-A-Pro"}, "Xiaomi", "mdi:television"),
        ({"primary_name": "Mi-Box-S", "vendor_name": "Xiaomi"}, "Xiaomi", "mdi:television-box"),
        ({"primary_name": "Mi-TV-Stick", "vendor_name": "Xiaomi"}, "Xiaomi", "mdi:television-box"),
        ({"primary_name": "MDZ-28-AA", "vendor_name": "Xiaomi"}, "Xiaomi", "mdi:television-box"),
    ]
    for host, exp_brand, exp_icon in samples:
        res = classify_lan_host(host, active=True)
        assert res.brand == exp_brand, f"Failed for {host}: got {res}"
        assert res.icon == exp_icon, f"Failed icon for {host}: got {res}"

    from custom_components.domolink_freebox_home.home_helpers import (
        asset_picture_url,
        resolve_repeater_model,
    )

    assert asset_picture_url("freebox_repeater_wifi7.png") == "/api/domolink_freebox_home/assets/freebox_repeater_wifi7.png"
    assert resolve_repeater_model({"has_6g": True}) == ("Répéteur Wi-Fi 7", "freebox_repeater_wifi7.png")
