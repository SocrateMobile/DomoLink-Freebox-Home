"""Async client for Freebox OS & Freebox Home APIs (fbxosapi)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
from typing import Any

import aiohttp

from .const import APP_ID, APP_NAME, APP_VERSION, DEVICE_NAME

_LOGGER = logging.getLogger(__name__)


class FreeboxOsError(Exception):
    """Generic Freebox OS API error."""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


class FreeboxAuthError(FreeboxOsError):
    """Authentication or permission error."""


def compute_hmac_password(app_token: str, challenge: str) -> str:
    """Compute HMAC-SHA1(app_token, challenge) required by POST login/session/."""
    return hmac.new(
        app_token.encode("utf-8"),
        challenge.encode("utf-8"),
        hashlib.sha1,
    ).hexdigest()


class FreeboxOsClient:
    """Async REST client for Freebox OS (local mafreebox.freebox.fr or remote HTTPS)."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int = 80,
        use_https: bool = False,
        app_id: str = APP_ID,
        app_token: str | None = None,
        api_version: str = "v11",
    ) -> None:
        self._session = session
        self.host = host
        self.port = port
        self.use_https = use_https
        self.app_id = app_id
        self.app_token = app_token
        self.api_version = api_version if api_version.startswith("v") else f"v{api_version}"
        self.session_token: str | None = None
        self.permissions: dict[str, bool] = {}
        self._auth_lock = asyncio.Lock()

    @property
    def base_origin(self) -> str:
        scheme = "https" if self.use_https else "http"
        return f"{scheme}://{self.host}:{self.port}"

    def _api_url(self, path: str) -> str:
        clean = path.lstrip("/")
        return f"{self.base_origin}/api/{self.api_version}/{clean}"

    async def async_get_api_version(self) -> dict[str, Any]:
        """Query /api_version without API prefix."""
        url = f"{self.base_origin}/api_version"
        try:
            async with self._session.get(
                url,
                ssl=False if self.use_https else None,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                major = str(data.get("api_version", "11")).split(".")[0]
                self.api_version = f"v{major}"
                return data
        except aiohttp.ClientError as err:
            raise FreeboxOsError(f"Cannot reach Freebox at {url}: {err}") from err

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        require_auth: bool = True,
        retry_auth: bool = True,
    ) -> Any:
        if require_auth and not self.session_token:
            await self.async_open_session()

        headers: dict[str, str] = {"Accept": "application/json"}
        if require_auth and self.session_token:
            headers["X-Fbx-App-Auth"] = self.session_token

        url = self._api_url(path)
        try:
            async with self._session.request(
                method,
                url,
                json=json_body,
                headers=headers,
                ssl=False if self.use_https else None,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                status_code = getattr(resp, "status", 200)
                try:
                    data = await resp.json()
                except (aiohttp.ContentTypeError, ValueError) as err:
                    raise FreeboxOsError(
                        f"[{method} {path}] Invalid response (HTTP {status_code})",
                        error_code=f"http_{status_code}",
                    ) from err
        except aiohttp.ClientError as err:
            raise FreeboxOsError(f"[{method} {path}] Network error: {err}") from err

        if not data.get("success", False):
            err_code = str(data.get("error_code", "unknown"))
            msg = str(data.get("msg", err_code))
            if (
                err_code in ("auth_required", "invalid_session")
                and require_auth
                and retry_auth
                and self.app_token
            ):
                self.session_token = None
                await self.async_open_session()
                return await self._request(
                    method,
                    path,
                    json_body=json_body,
                    require_auth=require_auth,
                    retry_auth=False,
                )
            if err_code in ("auth_required", "invalid_token", "insufficient_rights"):
                raise FreeboxAuthError(f"[{method} {path}] {msg}", error_code=err_code)
            raise FreeboxOsError(f"[{method} {path}] {msg}", error_code=err_code)

        return data.get("result")

    async def async_request_authorization(
        self,
        app_name: str = APP_NAME,
        app_version: str = APP_VERSION,
        device_name: str = DEVICE_NAME,
    ) -> tuple[str, int]:
        """Start physical pairing flow via POST login/authorize/."""
        result = await self._request(
            "POST",
            "login/authorize/",
            json_body={
                "app_id": self.app_id,
                "app_name": app_name,
                "app_version": app_version,
                "device_name": device_name,
            },
            require_auth=False,
            retry_auth=False,
        )
        self.app_token = result["app_token"]
        return str(result["app_token"]), int(result["track_id"])

    async def async_track_authorization(self, track_id: int) -> str:
        """Poll pairing status via GET login/authorize/{trackId}."""
        result = await self._request(
            "GET",
            f"login/authorize/{track_id}",
            require_auth=False,
            retry_auth=False,
        )
        return str(result.get("status", "unknown"))

    async def async_open_session(self) -> tuple[str, dict[str, bool]]:
        """Open a Freebox OS session using HMAC-SHA1(app_token, challenge)."""
        if not self.app_token:
            raise FreeboxAuthError("No app_token configured", error_code="invalid_token")

        async with self._auth_lock:
            if self.session_token:
                return self.session_token, self.permissions

            login_res = await self._request(
                "GET", "login", require_auth=False, retry_auth=False
            )
            challenge = str(login_res["challenge"])
            password = compute_hmac_password(self.app_token, challenge)

            sess_res = await self._request(
                "POST",
                "login/session/",
                json_body={"app_id": self.app_id, "password": password},
                require_auth=False,
                retry_auth=False,
            )
            self.session_token = str(sess_res["session_token"])
            self.permissions = {
                str(k): bool(v) for k, v in (sess_res.get("permissions") or {}).items()
            }
            return self.session_token, self.permissions

    async def async_get_system_config(self) -> dict[str, Any]:
        """Fetch Freebox system configuration & temperatures."""
        return await self._request("GET", "system/") or {}

    async def async_get_connection_status(self) -> dict[str, Any]:
        """Fetch WAN connection status & bitrates."""
        return await self._request("GET", "connection/") or {}

    async def _async_get_optional(self, path: str, default: Any) -> Any:
        """Fetch an optional hardware-dependent endpoint, degrading gracefully on 404/rights."""
        try:
            res = await self._request("GET", path)
            return default if res is None else res
        except FreeboxAuthError as err:
            if err.error_code == "insufficient_rights":
                _LOGGER.debug("Insufficient rights for optional endpoint %s: %s", path, err)
                return default
            raise
        except FreeboxOsError as err:
            _LOGGER.debug("Optional endpoint %s unavailable: %s", path, err)
            return default

    async def async_get_lte_aggregation(self) -> dict[str, Any]:
        """Fetch 4G/LTE aggregation status (Freebox Delta/Ultra)."""
        res = await self._async_get_optional("connection/lte/aggregation", {})
        return res if isinstance(res, dict) else {}

    async def async_get_repeaters(self) -> list[dict[str, Any]]:
        """Fetch paired Freebox Wi-Fi repeaters."""
        res = await self._async_get_optional("repeater/", [])
        return res if isinstance(res, list) else []

    async def async_get_home_nodes(self) -> list[dict[str, Any]]:
        """Fetch all Freebox Home / Security nodes (alarm, sensors, shutters, lights)."""
        res = await self._async_get_optional("home/nodes", [])
        return res if isinstance(res, list) else []

    async def async_get_home_endpoints_batch(
        self, requests: list[dict[str, int]]
    ) -> list[dict[str, Any]]:
        """Batch fetch current values for Home endpoints via POST home/endpoints/get."""
        if not requests:
            return []
        res = await self._request("POST", "home/endpoints/get", json_body=requests)
        return res if isinstance(res, list) else []

    async def async_set_home_endpoint(
        self, node_id: int, endpoint_id: int, value: Any
    ) -> bool:
        """Write an endpoint value via PUT home/endpoints/{nodeId}/{endpointId}."""
        await self._request(
            "PUT",
            f"home/endpoints/{node_id}/{endpoint_id}",
            json_body={"value": value},
        )
        return True

    async def async_get_cameras(self) -> list[dict[str, Any]]:
        """Fetch Freebox Home cameras with streamUrl."""
        res = await self._async_get_optional("camera/", [])
        return res if isinstance(res, list) else []

    async def async_get_camera_records(self, camera_id: str) -> list[dict[str, Any]]:
        """Fetch recorded clips for a camera."""
        res = await self._request("GET", f"camera/{camera_id}/records")
        return res if isinstance(res, list) else []

    async def async_reboot(self) -> bool:
        """Reboot the Freebox Server."""
        await self._request("POST", "system/reboot/")
        return True
