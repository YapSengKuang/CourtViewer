from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# How far ahead a scrape looks, in the course's local timezone.
WINDOW_DAYS = 14


def scrape_window(timezone_name: str, now: datetime) -> tuple[datetime, datetime]:
    """UTC bounds for [local midnight today, local midnight today + WINDOW_DAYS)."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    zone = ZoneInfo(timezone_name)
    local_start = now.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    local_end = local_start + timedelta(days=WINDOW_DAYS)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)
