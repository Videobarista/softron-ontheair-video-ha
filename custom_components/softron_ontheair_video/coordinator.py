"""Polling coordinator for Softron OnTheAir Video."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    OnTheAirVideoAuthError,
    OnTheAirVideoClient,
    OnTheAirVideoError,
)
from .const import DEFAULT_FPS, DOMAIN, PLAYLIST_REFRESH_EVERY
from .timecode import format_hhmmss, parse_timecode

_LOGGER = logging.getLogger(__name__)

# Softron has renamed and added payload keys across 4.x releases, so every
# value is looked up through a list of candidates instead of one fixed key.
_STATUS_KEYS = ("playback_status", "status", "playback_state", "state")
_PLAYING_KEYS = ("is_playing", "playing")
_PAUSED_KEYS = ("is_paused", "paused")
_TITLE_KEYS = (
    "item_display_name",
    "display_name",
    "clip_name",
    "name",
    "file_name",
    "filename",
    "title",
)
_ELAPSED_KEYS = (
    "elapsed_time_timecode",
    "elapsed_timecode",
    "elapsed_time",
    "elapsed",
    "current_time",
    "position",
    "playback_position",
)
_REMAINING_KEYS = (
    "remaining_time_timecode",
    "remaining_timecode",
    "remaining_time",
    "remaining",
    "clip_remaining_time",
)
_DURATION_KEYS = (
    "duration_timecode",
    "playback_duration",
    "duration",
    "chained_playback_duration",
    "non_chained_playback_duration",
)
_PLAYLIST_KEYS = (
    "playlist_display_name",
    "playlist_name",
    "playing_playlist_name",
    "document_name",
)
_PLAYLIST_ID_KEYS = ("playlist_unique_id", "playlist_uid", "unique_id")
_NEXT_KEYS = (
    "next_item_display_name",
    "play_next_item_display_name",
    "next_clip_display_name",
    "next_display_name",
)
_NEXT_LIVE_KEYS = ("next_live_display_name",)
_UNTIL_LIVE_KEYS = ("remaining_time_until_next_live",)
_FPS_KEYS = ("fps", "frame_rate", "framerate", "video_output_fps")
_VERSION_KEYS = ("version", "app_version", "application_version", "software_version")

_ITEM_CONTAINER_KEYS = ("current_item", "playing_item", "item", "playback", "clip")


def _walk(data: Any, depth: int = 0, max_depth: int = 3):
    """Yield every dict found in ``data``, shallowest first."""
    if depth > max_depth:
        return
    if isinstance(data, dict):
        yield data
        for value in data.values():
            if isinstance(value, dict):
                yield from _walk(value, depth + 1, max_depth)
    elif isinstance(data, list):
        for value in data[:5]:
            if isinstance(value, dict):
                yield from _walk(value, depth + 1, max_depth)


def _lookup(sources: list[Any], keys: tuple[str, ...]) -> Any:
    """Return the first non-empty value for ``keys`` found in ``sources``."""
    dicts = [d for source in sources for d in _walk(source)]
    for key in keys:
        for candidate in dicts:
            if key in candidate:
                value = candidate[key]
                if value not in (None, "", [], {}):
                    return value
    return None


@dataclass
class OnTheAirVideoData:
    """Normalised snapshot of one poll."""

    raw_playback: dict[str, Any] = field(default_factory=dict)
    raw_current_item: dict[str, Any] | None = None
    raw_playlists: list[dict[str, Any]] = field(default_factory=list)

    status: str | None = None
    is_playing: bool = False
    is_paused: bool = False
    title: str | None = None
    playlist: str | None = None
    next_title: str | None = None
    next_live: str | None = None
    fps: float = DEFAULT_FPS
    version: str | None = None

    elapsed: float | None = None
    remaining: float | None = None
    duration: float | None = None
    until_next_live: float | None = None
    position_updated_at: datetime | None = None

    @property
    def elapsed_timecode(self) -> str | None:
        """Elapsed time as HH:MM:SS."""
        return format_hhmmss(self.elapsed)

    @property
    def remaining_timecode(self) -> str | None:
        """Remaining time as HH:MM:SS."""
        return format_hhmmss(self.remaining)

    @property
    def duration_timecode(self) -> str | None:
        """Duration as HH:MM:SS."""
        return format_hhmmss(self.duration)


class OnTheAirVideoCoordinator(DataUpdateCoordinator[OnTheAirVideoData]):
    """Fetches and normalises the playback state."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: OnTheAirVideoClient,
        scan_interval: int,
        fallback_fps: float,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.entry = entry
        self.client = client
        self.fallback_fps = fallback_fps
        self._cycle = 0
        self._playlists: list[dict[str, Any]] = []
        self._logged_payload = False
        self._last_elapsed: float | None = None
        self._position_updated_at: datetime | None = None

    async def _async_update_data(self) -> OnTheAirVideoData:
        """Poll the application."""
        try:
            playback = await self.client.async_get_playback()
        except OnTheAirVideoAuthError as err:
            raise UpdateFailed(str(err)) from err
        except OnTheAirVideoError as err:
            raise UpdateFailed(str(err)) from err

        current_item: dict[str, Any] | None = None
        try:
            current_item = await self.client.async_get_current_item()
        except OnTheAirVideoError as err:
            _LOGGER.debug("No current item: %s", err)

        if self._cycle % PLAYLIST_REFRESH_EVERY == 0:
            try:
                self._playlists = await self.client.async_get_playlists()
            except OnTheAirVideoError as err:
                _LOGGER.debug("Playlist overview unavailable: %s", err)
        self._cycle += 1

        if not self._logged_payload:
            self._logged_payload = True
            _LOGGER.debug(
                "Raw payloads -- playback=%s current_item=%s playlists=%s",
                playback,
                current_item,
                self._playlists,
            )

        return self._build(playback, current_item, self._playlists)

    def _build(
        self,
        playback: dict[str, Any],
        current_item: dict[str, Any] | None,
        playlists: list[dict[str, Any]],
    ) -> OnTheAirVideoData:
        """Turn the raw payloads into a normalised snapshot."""
        # The item dict is searched first so its title wins over any
        # playlist-level name.
        item_sources: list[Any] = []
        if current_item:
            item_sources.append(current_item)
        for key in _ITEM_CONTAINER_KEYS:
            value = playback.get(key)
            if isinstance(value, dict):
                item_sources.append(value)
        sources: list[Any] = [*item_sources, playback]

        fps = parse_timecode(_lookup(sources, _FPS_KEYS)) or self.fallback_fps
        if fps <= 0:
            fps = self.fallback_fps

        status_raw = _lookup(sources, _STATUS_KEYS)
        status = str(status_raw).lower() if status_raw is not None else None

        is_playing = bool(_lookup(sources, _PLAYING_KEYS))
        is_paused = bool(_lookup(sources, _PAUSED_KEYS))
        if status:
            if "paus" in status:
                is_paused = True
            elif "play" in status or "run" in status:
                is_playing = True
            elif "stop" in status or "idle" in status:
                is_playing = False

        elapsed = parse_timecode(_lookup(sources, _ELAPSED_KEYS), fps)
        remaining = parse_timecode(_lookup(sources, _REMAINING_KEYS), fps)
        duration = parse_timecode(_lookup(sources, _DURATION_KEYS), fps)

        if duration is None and elapsed is not None and remaining is not None:
            duration = elapsed + abs(remaining)
        if elapsed is None and duration is not None and remaining is not None:
            elapsed = max(duration - abs(remaining), 0.0)

        if elapsed != self._last_elapsed:
            self._last_elapsed = elapsed
            self._position_updated_at = dt_util.utcnow()

        playlist = _lookup(sources, _PLAYLIST_KEYS)
        if playlist is None:
            playlist_id = _lookup(sources, _PLAYLIST_ID_KEYS)
            for entry in playlists:
                if playlist_id and entry.get("unique_id") == playlist_id:
                    playlist = entry.get("display_name") or entry.get("name")
                    break
            else:
                if len(playlists) == 1:
                    playlist = playlists[0].get("display_name") or playlists[0].get(
                        "name"
                    )

        return OnTheAirVideoData(
            raw_playback=playback,
            raw_current_item=current_item,
            raw_playlists=playlists,
            status=str(status_raw) if status_raw is not None else None,
            is_playing=is_playing and not is_paused,
            is_paused=is_paused,
            title=_str_or_none(_lookup(item_sources or sources, _TITLE_KEYS)),
            playlist=_str_or_none(playlist),
            next_title=_str_or_none(_lookup([playback], _NEXT_KEYS)),
            next_live=_str_or_none(_lookup([playback], _NEXT_LIVE_KEYS)),
            fps=fps,
            version=_str_or_none(_lookup([playback], _VERSION_KEYS)),
            elapsed=elapsed,
            remaining=remaining,
            duration=duration,
            until_next_live=parse_timecode(
                _lookup([playback], _UNTIL_LIVE_KEYS), fps
            ),
            position_updated_at=self._position_updated_at,
        )


def _str_or_none(value: Any) -> str | None:
    """Return ``value`` as a stripped string, or None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None
