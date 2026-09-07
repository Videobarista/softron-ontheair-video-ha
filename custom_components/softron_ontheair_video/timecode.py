"""Timecode helpers.

OnTheAir Video mixes representations in its REST/WebSocket payloads:

* plain seconds as a number          -> ``10.05``
* seconds as a string                -> ``"10.05"``
* wall clock strings                 -> ``"00:00:10"``
* SMPTE timecode with frames         -> ``"01:02:03:12"``
* SMPTE drop frame (semicolon)       -> ``"01:02:03;12"``
* fractional seconds                 -> ``"00:01:02.500"``
* negative values (countdowns)       -> ``"-00:00:05"``

Home Assistant expects ``media_position`` / ``media_duration`` in whole
seconds, so everything is normalised to float seconds here.
"""

from __future__ import annotations

import re
from typing import Any

# hh:mm:ss[:ff | ;ff][.fraction]  --  the hours group is optional (mm:ss)
_TC_RE = re.compile(
    r"^(?P<sign>[-+])?"
    r"(?:(?P<first>\d{1,4}):)?"
    r"(?P<second>\d{1,3}):"
    r"(?P<third>\d{1,3})"
    r"(?:[:;](?P<frames>\d{1,3}))?"
    r"(?:[.,](?P<fraction>\d{1,6}))?$"
)


def parse_timecode(value: Any, fps: float = 25.0) -> float | None:
    """Return ``value`` as seconds, or ``None`` when it cannot be parsed.

    ``fps`` is only used when the value carries a frame count.
    """
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    # Plain "12.5" style values.
    try:
        return float(text)
    except ValueError:
        pass

    match = _TC_RE.match(text)
    if match is None:
        return None

    groups = match.groupdict()

    if groups["first"] is not None:
        hours = int(groups["first"])
        minutes = int(groups["second"])
        seconds = int(groups["third"])
    else:
        hours = 0
        minutes = int(groups["second"])
        seconds = int(groups["third"])

    total = float(hours * 3600 + minutes * 60 + seconds)

    if groups["frames"] is not None:
        rate = fps if fps and fps > 0 else 25.0
        total += int(groups["frames"]) / rate

    if groups["fraction"] is not None:
        total += float("0." + groups["fraction"])

    if groups["sign"] == "-":
        total = -total

    return total


def looks_like_timecode(value: Any) -> bool:
    """Return True when ``value`` is a colon separated timecode string."""
    return isinstance(value, str) and _TC_RE.match(value.strip()) is not None


def format_hhmmss(seconds: float | None) -> str | None:
    """Format seconds as ``HH:MM:SS`` (negative values keep their sign)."""
    if seconds is None:
        return None

    sign = "-" if seconds < 0 else ""
    total = int(abs(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{sign}{hours:02d}:{minutes:02d}:{secs:02d}"
