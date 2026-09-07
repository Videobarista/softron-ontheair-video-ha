"""Constants for the Softron OnTheAir Video integration."""

from __future__ import annotations

DOMAIN = "softron_ontheair_video"

MANUFACTURER = "Softron"
MODEL = "OnTheAir Video"

CONF_USE_HTTPS = "use_https"
CONF_VERIFY_SSL = "verify_ssl"
CONF_FPS = "fps"
CONF_THUMBNAIL = "thumbnail"

DEFAULT_NAME = "OnTheAir Video"
DEFAULT_PORT = 8081
DEFAULT_SCAN_INTERVAL = 2
DEFAULT_FPS = 25.0
DEFAULT_TIMEOUT = 10

# Only fetch the playlist overview every N updates: it is the heaviest call
# and its content changes rarely compared to the playback status.
PLAYLIST_REFRESH_EVERY = 15
