"""The date and time the kindergarten's books go by: Syria (Asia/Damascus), not the clock of the server.

Business dates (a booking day, the end of a month, closing a month, counting the cash box) come from `local_today()`.
Time stamps that are stored stay in UTC. APP_TIMEZONE changes the zone ("LOCAL" = the clock of this computer, used by the tests).
"""

from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

DEFAULT_ZONE = "Asia/Damascus"


def zone_name() -> str:
    return os.getenv("APP_TIMEZONE", DEFAULT_ZONE) or DEFAULT_ZONE


def local_now() -> datetime:
    name = zone_name()
    if name == "LOCAL":
        return datetime.now().astimezone()
    return datetime.now(ZoneInfo(name))


def local_today() -> date:
    return local_now().date()


def to_local(moment: datetime) -> datetime:
    """A stored UTC time stamp as local time (for showing). A naive value is taken as UTC."""
    from datetime import timezone

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    name = zone_name()
    return moment.astimezone() if name == "LOCAL" else moment.astimezone(ZoneInfo(name))
