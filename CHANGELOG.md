# Changelog

## v0.1.0 - 2026-09-07

First release.

### Added
- Config flow: host, port, optional name, optional username/password (HTTP Basic), optional HTTPS.
- Media player entity: playing / paused / idle / off, current clip title, playlist, position and duration, play, pause, stop, next and previous clip.
- Video output thumbnail (`GET /playback/thumbnail`) used as media artwork.
- Sensors: playback status, current clip, playlist, next clip, elapsed, remaining, clip duration, next live, frame rate.
- Timecode parser handling seconds, `HH:MM:SS`, SMPTE `HH:MM:SS:FF`, drop frame `HH:MM:SS;FF`, fractional seconds and negative countdowns; frame counts converted with the reported frame rate, falling back to a configurable value.
- Options flow: polling interval, fallback frame rate, thumbnail on/off.
- Diagnostics download containing the raw REST payloads next to the parsed values.
- Dutch and English translations.

### Notes
- Commands are sent as GET first and fall back to PUT and POST, since Softron changed verbs across 4.x releases. The accepted verb is cached per endpoint.
- Payload keys are matched against a list of known aliases, so renamed fields across OnTheAir Video versions do not break the entities.
- The media player reports `off` instead of `unavailable` when the application cannot be reached.
