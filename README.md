# Softron OnTheAir Video for Home Assistant

Turns a [Softron OnTheAir Video](https://softron.tv/products/play/ontheair-video)
playout channel into a Home Assistant media player, using the built-in REST API
(default port 8081).

Not affiliated with Softron Media Services.

## What you get

| Entity | Notes |
| --- | --- |
| `media_player` | State (playing / paused / idle / off), current clip, playlist, position and duration, play / pause / stop / next / previous, video output thumbnail as artwork |
| Sensors | Playback status, current clip, playlist, next clip, elapsed, remaining, clip duration (disabled by default), next live (disabled by default), frame rate (disabled by default) |

Elapsed, remaining and duration are exposed twice: as seconds (so they work in
automations, templates and history graphs) and as a `timecode` attribute in
`HH:MM:SS` form for dashboards.

## Timecode handling

OnTheAir Video mixes representations in its payloads. Everything is normalised
to seconds before it reaches Home Assistant:

| Input | Result |
| --- | --- |
| `10.05` | 10.05 s |
| `"00:00:10"` | 10 s |
| `"01:02:03:12"` (SMPTE, frames) | 3723.48 s at 25 fps |
| `"01:02:03;12"` (drop frame) | same, semicolon accepted |
| `"00:01:02.500"` | 62.5 s |
| `"-00:00:05"` (countdown) | -5 s |

Frame counts are converted with the frame rate reported by the application. If
it does not report one, the fallback in the integration options is used
(default 25 fps).

## Requirements

* OnTheAir Video 4.x (**not** OnTheAir Video Express — the REST API is not
  available in Express)
* In OnTheAir Video: *Settings > General > HTTP Server* > enable **Remote
  Control**
* If authentication is enabled there, fill in the same username and password
  when adding the integration

For a "multi" installation, use one config entry per instance: port 8081 for
OnTheAir Video 1, 8082 for 2, and so on.

## Installation

### HACS (custom repository)

1. HACS > three dots > **Custom repositories**
2. URL: `https://github.com/HuisAutomatisering/softron-ontheair-video-ha`,
   category **Integration**
3. Install, restart Home Assistant
4. *Settings > Devices & services > Add integration* > **Softron OnTheAir Video**

### Manual

Copy `custom_components/softron_ontheair_video` into your `config/custom_components`
folder and restart Home Assistant.

## Options

* **Polling interval** — default 2 seconds
* **Fallback frame rate** — used only when the application does not report one
* **Show video output thumbnail** — turn off if `/playback/thumbnail` is not
  available or too heavy on your setup

## Known limitations

* Seeking is not implemented yet: the exact endpoint differs per version.
* Playlist selection (`media_player.play_media`) is not implemented yet.
* Updates are polled. A WebSocket connection (`ws://host:8081/playback`,
  protocol `playback_update_v1`) is planned so state changes arrive instantly.
* Softron publishes the full API only from the running application
  (`http://<host>:8081/api.html`), so field names are matched against a list of
  known aliases. If something stays empty, download the integration
  diagnostics: they contain the raw payloads.

## License

MIT
