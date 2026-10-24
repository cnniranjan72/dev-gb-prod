from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
UTC = timezone.utc
HALF_HOUR_MINUTES = 30


def to_utc(value: str | datetime) -> datetime:
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        value = datetime.fromisoformat(text)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def iso_utc(value: str | datetime) -> str:
    return to_utc(value).isoformat().replace("+00:00", "Z")


def iso_london(value: str | datetime) -> str:
    return to_utc(value).astimezone(LONDON).isoformat()


def settlement_date_local(interval_start_utc: str | datetime) -> datetime:
    """Europe/London settlement date of a half-hour interval.

    Elexon emits `settlementDate` in GB-local terms: a 23:30Z summer interval
    belongs to the next London day (period 1). Using the interval mid-point to
    pick the London date avoids ambiguity at DST boundaries both ways.
    """
    midpoint = to_utc(interval_start_utc) + timedelta(minutes=15)
    return midpoint.astimezone(LONDON).date()


def floor_to_hour(moment: str | datetime) -> datetime:
    return to_utc(moment).replace(minute=0, second=0, microsecond=0)


def hour_end_label(interval_start_utc: str | datetime) -> datetime:
    """WINDFOR startTime T labels the hour ending at T (empirically resolved).

    See docs/DATA_INVESTIGATION.md; the snapshot retains the raw source label
    so the alternative forward-hour reading can be re-derived.
    """
    return floor_to_hour(interval_start_utc) + timedelta(hours=1)


def london_date_to_utc_window(delivery_date: date) -> tuple[datetime, datetime]:
    """UTC start/end times of a GB-local settlement date."""
    start_local = datetime(delivery_date.year, delivery_date.month, delivery_date.day, tzinfo=LONDON)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)
