"""Diagnostics for Softron OnTheAir Video."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import OnTheAirVideoCoordinator

TO_REDACT = {CONF_HOST, CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics, including the raw API payloads."""
    coordinator: OnTheAirVideoCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "raw": {
            "playback": data.raw_playback if data else None,
            "current_item": data.raw_current_item if data else None,
            "playlists": data.raw_playlists if data else None,
        },
        "parsed": {
            "status": data.status if data else None,
            "is_playing": data.is_playing if data else None,
            "is_paused": data.is_paused if data else None,
            "title": data.title if data else None,
            "playlist": data.playlist if data else None,
            "elapsed": data.elapsed if data else None,
            "remaining": data.remaining if data else None,
            "duration": data.duration if data else None,
            "fps": data.fps if data else None,
        },
    }
