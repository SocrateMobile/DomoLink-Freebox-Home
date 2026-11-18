"""Unit tests for DomoLink Freebox Home API client and home node mapping."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hashlib
import hmac
from pathlib import Path
import sys
import types

import pytest

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
    SELECT="select",
    UPDATE="update",
)
ha_const.CONF_HOST = "host"
ha_const.CONF_PORT = "port"
ha_core = types.ModuleType("homeassistant.core")
ha_core.HomeAssistant = object
ha_core.ServiceCall = object
ha_core.callback = lambda fn: fn
ha_ce = types.ModuleType("homeassistant.config_entries")
ha_ce.ConfigEntry = object
ha_exc = types.ModuleType("homeassistant.exceptions")
ha_exc.ConfigEntryAuthFailed = type("ConfigEntryAuthFailed", (Exception,), {})
ha_helpers = types.ModuleType("homeassistant.helpers")
ha_er = types.ModuleType("homeassistant.helpers.entity_registry")
ha_er.async_get = lambda hass: None
ha_er.async_entries_for_config_entry = lambda reg, eid: []
ha_er.RegistryEntryDisabler = types.SimpleNamespace(INTEGRATION="integration")
ha_helpers.entity_registry = ha_er
ha_aio = types.ModuleType("homeassistant.helpers.aiohttp_client")
ha_aio.async_get_clientsession = lambda hass: None
ha_dr = types.ModuleType("homeassistant.helpers.device_registry")
ha_dr.DeviceInfo = dict
ha_dr.CONNECTION_NETWORK_MAC = "mac"
ha_dr.async_get = lambda hass: None
ha_helpers.device_registry = ha_dr
ha_uc = types.ModuleType("homeassistant.helpers.update_coordinator")
ha_uc.DataUpdateCoordinator = type("DataUpdateCoordinator", (), {"__class_getitem__": classmethod(lambda cls, item: cls)})
ha_uc.CoordinatorEntity = type("CoordinatorEntity", (), {"__class_getitem__": classmethod(lambda cls, item: cls)})
ha_uc.UpdateFailed = type("UpdateFailed", (Exception,), {})

for name, mod in [
    ("homeassistant", ha_pkg),
    ("homeassistant.const", ha_const),
    ("homeassistant.core", ha_core),
    ("homeassistant.config_entries", ha_ce),
    ("homeassistant.exceptions", ha_exc),
    ("homeassistant.helpers", ha_helpers),
    ("homeassistant.helpers.entity_registry", ha_er),
    ("homeassistant.helpers.aiohttp_client", ha_aio),
    ("homeassistant.helpers.device_registry", ha_dr),
    ("homeassistant.helpers.update_coordinator", ha_uc),
]:
    sys.modules.setdefault(name, mod)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from custom_components.domolink_freebox_home.api import (  # noqa: E402
    FreeboxAuthError,
    FreeboxOsClient,
    FreeboxOsError,
    compute_hmac_password,
)
from custom_components.domolink_freebox_home.home_helpers import find_endpoint  # noqa: E402


class FakeResponse:
    def __init__(self, json_data: dict | None = None, status: int = 200) -> None:
        self._json = json_data
        self.status = status

    async def json(self) -> dict:
        if self._json is None:
            raise ValueError("not json")
        return self._json


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def request(self, method: str, url: str, **kwargs):
        self.calls.append((method, url, kwargs))
        resp = self._responses.pop(0)

        @asynccontextmanager
        async def _cm():
            yield resp

        return _cm()


def test_compute_hmac_password():
    token = "my_app_token"
    challenge = "my_challenge"
    expected = hmac.new(token.encode(), challenge.encode(), hashlib.sha1).hexdigest()
    assert compute_hmac_password(token, challenge) == expected


def test_pairing_and_open_session():
    session = FakeSession([
        FakeResponse({"api_version": "14.0", "box_model_name": "Freebox Ultra", "uid": "box-1"}),
        FakeResponse({"success": True, "result": {"app_token": "tok-1", "track_id": 99}}),
        FakeResponse({"success": True, "result": {"status": "granted"}}),
        FakeResponse({"success": True, "result": {"challenge": "chal-1"}}),
        FakeResponse({"success": True, "result": {"session_token": "sess-1", "permissions": {"home": True, "cameras": True}}}),
    ])
    client = FreeboxOsClient(session, host="mafreebox.freebox.fr")

    ver = asyncio.run(client.async_get_api_version())
    assert ver["uid"] == "box-1"
    assert client.api_version == "v14"

    tok, track = asyncio.run(client.async_request_authorization())
    assert tok == "tok-1" and track == 99

    status = asyncio.run(client.async_track_authorization(99))
    assert status == "granted"

    sess, perms = asyncio.run(client.async_open_session())
    assert sess == "sess-1"
    assert perms["home"] is True
    assert session.calls[4][2]["json"]["password"] == compute_hmac_password("tok-1", "chal-1")


def test_auth_required_reopens_session_and_retries():
    session = FakeSession([
        FakeResponse({"success": False, "error_code": "auth_required", "msg": "Auth required"}),
        FakeResponse({"success": True, "result": {"challenge": "chal-2"}}),
        FakeResponse({"success": True, "result": {"session_token": "sess-2", "permissions": {"home": True}}}),
        FakeResponse({"success": True, "result": {"board_name": "fbxgw9r"}}),
    ])
    client = FreeboxOsClient(session, host="mafreebox.freebox.fr", app_token="tok-1")
    client.session_token = "expired-sess"

    sys_cfg = asyncio.run(client.async_get_system_config())
    assert sys_cfg["board_name"] == "fbxgw9r"
    assert client.session_token == "sess-2"


def test_find_endpoint_helper():
    node = {
        "id": 7,
        "label": "Volet Salon",
        "show_endpoints": [
            {"id": 1, "name": "position", "ep_type": "signal", "value": 50},
            {"id": 2, "name": "position_set", "ep_type": "slot"},
        ],
    }
    ep_sig = find_endpoint(node, name="position", ep_type="signal")
    ep_slot = find_endpoint(node, name="position_set", ep_type="slot")
    assert ep_sig is not None and ep_sig["value"] == 50
    assert ep_slot is not None and ep_slot["id"] == 2


def test_optional_endpoints_degrade_gracefully_on_404():
    err_404 = {"success": False, "error_code": "invalid_request", "msg": "Requête invalide (404)"}
    session = FakeSession([
        FakeResponse(err_404, status=404),
        FakeResponse(err_404, status=404),
        FakeResponse(err_404, status=404),
        FakeResponse(err_404, status=404),
    ])
    client = FreeboxOsClient(session, host="mafreebox.freebox.fr", app_token="tok-1")
    client.session_token = "sess-1"

    assert asyncio.run(client.async_get_home_nodes()) == []
    assert asyncio.run(client.async_get_cameras()) == []
    assert asyncio.run(client.async_get_repeaters()) == []
    assert asyncio.run(client.async_get_lte_aggregation()) == {}


def test_required_system_endpoint_raises_with_path():
    session = FakeSession([
        FakeResponse({"success": False, "error_code": "invalid_request", "msg": "Requête invalide (404)"}, status=404),
    ])
    client = FreeboxOsClient(session, host="mafreebox.freebox.fr", app_token="tok-1")
    client.session_token = "sess-1"

    with pytest.raises(FreeboxOsError) as exc:
        asyncio.run(client.async_get_system_config())
    assert "[GET system/]" in str(exc.value)


def test_non_json_404_response_handled():
    session = FakeSession([FakeResponse(None, status=404)])
    client = FreeboxOsClient(session, host="mafreebox.freebox.fr", app_token="tok-1")
    client.session_token = "sess-1"

    with pytest.raises(FreeboxOsError) as exc:
        asyncio.run(client.async_get_system_config())
    assert "HTTP 404" in str(exc.value)
