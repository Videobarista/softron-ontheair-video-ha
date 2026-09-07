"""Media player for Softron OnTheAir Video."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import OnTheAirVideoError
from .const import CONF_THUMBNAIL, DOMAIN, MANUFACTURER, MODEL
from .coordinator import OnTheAirVideoCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the media player."""
    coordinator: OnTheAirVideoCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OnTheAirVideoMediaPlayer(coordinator, entry)])


class OnTheAirVideoMediaPlayer(
    CoordinatorEntity[OnTheAirVideoCoordinator], MediaPlayerEntity
):
    """Represents the playout channel."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_media_content_type = MediaType.VIDEO
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
    )

    def __init__(
        self, coordinator: OnTheAirVideoCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_media_player"
        self._thumbnails_enabled = entry.options.get(CONF_THUMBNAIL, True)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=coordinator.client.base_url,
        )

    @property
    def available(self) -> bool:
        """Stay available so the entity can report 'off' when unreachable."""
        return True

    @property
    def state(self) -> MediaPlayerState:
        """Return the playback state."""
        if not self.coordinator.last_update_success:
            return MediaPlayerState.OFF
        data = self.coordinator.data
        if data is None:
            return MediaPlayerState.OFF
        if data.is_paused:
            return MediaPlayerState.PAUSED
        if data.is_playing:
            return MediaPlayerState.PLAYING
        return MediaPlayerState.IDLE

    @property
    def media_title(self) -> str | None:
        """Return the currently playing clip."""
        data = self.coordinator.data
        return data.title if data else None

    @property
    def media_playlist(self) -> str | None:
        """Return the playlist the clip belongs to."""
        data = self.coordinator.data
        return data.playlist if data else None

    @property
    def media_duration(self) -> int | None:
        """Return the clip duration in seconds."""
        data = self.coordinator.data
        if data is None or data.duration is None:
            return None
        return int(round(abs(data.duration)))

    @property
    def media_position(self) -> int | None:
        """Return the playback position in seconds."""
        data = self.coordinator.data
        if data is None or data.elapsed is None:
            return None
        return int(round(max(data.elapsed, 0.0)))

    @property
    def media_position_updated_at(self):
        """Return when the position was last updated."""
        data = self.coordinator.data
        return data.position_updated_at if data else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return timecode friendly extras."""
        data = self.coordinator.data
        if data is None:
            return {}
        return {
            "playback_status": data.status,
            "elapsed_timecode": data.elapsed_timecode,
            "remaining_timecode": data.remaining_timecode,
            "duration_timecode": data.duration_timecode,
            "remaining_seconds": (
                None if data.remaining is None else round(abs(data.remaining), 2)
            ),
            "playlist": data.playlist,
            "next_clip": data.next_title,
            "next_live": data.next_live,
            "fps": data.fps,
        }

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Return a snapshot of the video output."""
        if not self._thumbnails_enabled:
            return None, None
        try:
            result = await self.coordinator.client.async_get_thumbnail()
        except OnTheAirVideoError as err:
            _LOGGER.debug("Thumbnail unavailable: %s", err)
            return None, None
        if result is None:
            return None, None
        return result

    async def _async_send(self, coro) -> None:
        """Run a command and log failures instead of raising a traceback."""
        try:
            await coro
        except OnTheAirVideoError as err:
            _LOGGER.debug("Command refused by OnTheAir Video: %s", err)
            return
        await self.coordinator.async_request_refresh()

    async def async_media_play(self) -> None:
        """Start playback."""
        await self._async_send(self.coordinator.client.async_play())

    async def async_media_pause(self) -> None:
        """Pause playback."""
        await self._async_send(self.coordinator.client.async_pause())

    async def async_media_stop(self) -> None:
        """Stop playback."""
        await self._async_send(self.coordinator.client.async_stop())

    async def async_media_next_track(self) -> None:
        """Skip to the next clip."""
        await self._async_send(self.coordinator.client.async_skip_next())

    async def async_media_previous_track(self) -> None:
        """Skip to the previous clip."""
        await self._async_send(self.coordinator.client.async_skip_previous())
