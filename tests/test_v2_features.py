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
    BUTTON="button",
    DEVICE_TRACKER="device_tracker",
    NUMBER="number",
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
