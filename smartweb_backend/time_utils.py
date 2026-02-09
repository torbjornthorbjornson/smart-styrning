from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

DEFAULT_TZNAME = "Europe/Stockholm"


def get_tz(tzname: str = DEFAULT_TZNAME) -> ZoneInfo:
    return ZoneInfo(tzname)


def utc_now_naive() -> datetime:
    """UTC time as naive datetime (matches MariaDB DATETIME usage in this project)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def today_local_date(tzname: str = DEFAULT_TZNAME) -> date:
    """Today's calendar date in the given local timezone (default: Sweden)."""
    tz = get_tz(tzname)
    return datetime.now(timezone.utc).astimezone(tz).date()


def local_day_to_utc_window(local_day: date, tzname: str = DEFAULT_TZNAME) -> tuple[datetime, datetime]:
    """Return (utc_start, utc_end) as naive UTC datetimes for one local calendar day.

    The DB stores timestamps as UTC-naive DATETIME. This helper produces a UTC-naive
    half-open interval [utc_start, utc_end) corresponding to local 00:00–24:00.
    """
    tz = get_tz(tzname)
    start_local = datetime.combine(local_day, time(0, 0), tzinfo=tz)
    end_local = start_local + timedelta(days=1)

    utc_start = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    utc_end = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    return utc_start, utc_end


def utc_naive_to_local(dt_utc_naive: datetime, tzname: str = DEFAULT_TZNAME) -> datetime:
    """Convert a UTC-naive datetime (from DB) to a timezone-aware local datetime."""
    tz = get_tz(tzname)
    return dt_utc_naive.replace(tzinfo=timezone.utc).astimezone(tz)


def utc_naive_to_local_label(
    dt_utc_naive: datetime,
    fmt: str = "%H:%M",
    tzname: str = DEFAULT_TZNAME,
) -> str:
    return utc_naive_to_local(dt_utc_naive, tzname=tzname).strftime(fmt)
