from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Include today and the date exactly two weeks ahead (offsets 0 through 14).
WINDOW_DAYS = 15


def scrape_window(timezone_name: str, now: datetime) -> tuple[datetime, datetime]:
    """UTC bounds including all of local today + 14 days; excludes day + 15."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    zone = ZoneInfo(timezone_name)
    local_start = now.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    local_end = local_start + timedelta(days=WINDOW_DAYS)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)
