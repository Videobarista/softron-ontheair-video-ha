"""Small async client for the OnTheAir Video REST API (default port 8081)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from aiohttp import ClientResponseError, ClientSession

from .const import DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)

# Softron documents its control calls as plain GET requests
# (e.g. /playback/skip_next?live_only=1). Older/newer builds have used PUT
# and POST as well, so every command falls back until one is accepted.
_COMMAND_METHODS = ("GET", "PUT", "POST")
_METHOD_NOT_SUPPORTED = (404, 405, 501)


class OnTheAirVideoError(Exception):
    """Generic error talking to OnTheAir Video."""


class OnTheAirVideoConnectionError(OnTheAirVideoError):
    """The application could not be reached."""


class OnTheAirVideoAuthError(OnTheAirVideoError):
    """Authentication failed or is required."""


class OnTheAirVideoClient:
    """Talks to one OnTheAir Video instance."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        port: int = 8081,
        username: str | None = None,
        password: str | None = None,
        use_https: bool = False,
        verify_ssl: bool = False,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialise the client."""
        self._session = session
        self._host = host
        self._port = port
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._verify_ssl = verify_ssl
        self._scheme = "https" if use_https else "http"
        self._auth: aiohttp.BasicAuth | None = None
        if username:
            self._auth = aiohttp.BasicAuth(username, password or "")
        # Remembers which HTTP verb a command endpoint accepted.
        self._verb_cache: dict[str, str] = {}

    @property
    def base_url(self) -> str:
        """Return the base URL of the instance."""
        return f"{self._scheme}://{self._host}:{self._port}"

    def url(self, path: str) -> str:
        """Return an absolute URL for ``path``."""
        return f"{self.base_url}/{path.lstrip('/')}"

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        raise_for_status: bool = True,
    ) -> aiohttp.ClientResponse:
        """Perform a single request and return the raw response."""
        try:
            response = await self._session.request(
                method,
                self.url(path),
                params=params,
                auth=self._auth,
                timeout=self._timeout,
                ssl=self._verify_ssl if self._scheme == "https" else None,
            )
        except asyncio.TimeoutError as err:
            raise OnTheAirVideoConnectionError(f"Timeout on {path}") from err
        except aiohttp.ClientError as err:
            raise OnTheAirVideoConnectionError(f"Cannot reach {path}: {err}") from err

        if response.status in (401, 403):
            response.release()
            raise OnTheAirVideoAuthError(
                "OnTheAir Video refused the credentials (HTTP %s)" % response.status
            )

        if raise_for_status and response.status >= 400:
            response.release()
            raise OnTheAirVideoError(f"HTTP {response.status} on {path}")

        return response

    async def _get_json(
        self, path: str, params: dict[str, Any] | None = None
    ) -> Any:
        """GET ``path`` and decode the JSON body."""
        response = await self._request("GET", path, params)
        try:
            return await response.json(content_type=None)
        except (ValueError, ClientResponseError) as err:
            raise OnTheAirVideoError(f"Invalid JSON from {path}: {err}") from err
        finally:
            response.release()

    async def _command(
        self, path: str, params: dict[str, Any] | None = None
    ) -> None:
        """Fire a control command, discovering the accepted HTTP verb once."""
        methods = (
            (self._verb_cache[path],)
            if path in self._verb_cache
            else _COMMAND_METHODS
        )

        last_status: int | None = None
        for method in methods:
            response = await self._request(
                method, path, params, raise_for_status=False
            )
            status = response.status
            response.release()

            if status < 400:
                self._verb_cache[path] = method
                _LOGGER.debug("Command %s %s -> HTTP %s", method, path, status)
                return

            last_status = status
            if status not in _METHOD_NOT_SUPPORTED:
                # The endpoint exists but rejected the request; do not keep
                # hammering it with other verbs.
                break

        raise OnTheAirVideoError(f"Command {path} failed (HTTP {last_status})")

    # -- reads ---------------------------------------------------------

    async def async_get_playback(self) -> dict[str, Any]:
        """Return the playback status."""
        data = await self._get_json("/playback")
        return data if isinstance(data, dict) else {"value": data}

    async def async_get_current_item(self) -> dict[str, Any] | None:
        """Return the currently playing item, if any."""
        data = await self._get_json("/playback/current_item/")
        return data if isinstance(data, dict) else None

    async def async_get_playlists(self) -> list[dict[str, Any]]:
        """Return the list of open playlists."""
        data = await self._get_json("/playlists")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("playlists", "items", "documents"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    async def async_get_thumbnail(self) -> tuple[bytes, str] | None:
        """Return a JPEG snapshot of the video output."""
        response = await self._request(
            "GET", "/playback/thumbnail", raise_for_status=False
        )
        try:
            if response.status >= 400:
                return None
            content_type = response.headers.get("Content-Type", "image/jpeg")
            return await response.read(), content_type
        finally:
            response.release()

    # -- controls ------------------------------------------------------

    async def async_play(self) -> None:
        """Start playback."""
        await self._command("/playback/play")

    async def async_pause(self) -> None:
        """Pause playback."""
        await self._command("/playback/pause")

    async def async_stop(self) -> None:
        """Stop playback."""
        await self._command("/playback/stop")

    async def async_skip_next(self, live_only: bool = False) -> None:
        """Skip to the next clip."""
        params = {"live_only": "1"} if live_only else None
        await self._command("/playback/skip_next", params)

    async def async_skip_previous(self) -> None:
        """Skip to the previous clip."""
        await self._command("/playback/skip_previous")

    async def async_check_connection(self) -> dict[str, Any]:
        """Validate host, port and credentials."""
        return await self.async_get_playback()
