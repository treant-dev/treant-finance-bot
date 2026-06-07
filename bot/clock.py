"""Timezone-aware current date/time for the configured zone.

The bot runs on a UTC server, so all "today"/"now" logic must go through here to
reflect the user's local day (e.g. a late-night expense should land on the right date).
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

_tz = ZoneInfo("Europe/Belgrade")


def configure(tz_name: str) -> None:
    global _tz
    _tz = ZoneInfo(tz_name)


def now() -> dt.datetime:
    return dt.datetime.now(_tz)


def today() -> dt.date:
    return now().date()
