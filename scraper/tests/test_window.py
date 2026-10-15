from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from golf_scraper.spiders.miclub import MiClubSpider
from golf_scraper.window import scrape_window


@pytest.mark.parametrize("zone_name", ["Australia/Melbourne", "America/Los_Angeles"])
def test_window_includes_all_of_day_fourteen(zone_name):
    zone = ZoneInfo(zone_name)
    now = datetime(2026, 10, 16, 12, tzinfo=zone)
    start, end = scrape_window(zone_name, now)
    assert start.astimezone(zone).date() == now.date()
    assert end.astimezone(zone) == datetime(2026, 10, 31, tzinfo=zone)
    last_included = datetime(2026, 10, 30, 23, 59, 59, tzinfo=zone)
    assert start <= last_included < end
    assert start.tzinfo == end.tzinfo == timezone.utc


def test_horizon_rolls_at_course_local_midnight():
    before = datetime(2026, 10, 16, 12, 59, tzinfo=timezone.utc)
    after = before + timedelta(minutes=1)  # Melbourne midnight, not UTC midnight.
    first = scrape_window("Australia/Melbourne", before)
    second = scrape_window("Australia/Melbourne", after)
    assert second[0] - first[0] == timedelta(days=1)
    assert second[1] - first[1] == timedelta(days=1)


def test_window_preserves_local_midnight_across_daylight_saving():
    start, end = scrape_window(
        "Australia/Melbourne", datetime(2026, 9, 28, tzinfo=timezone.utc)
    )
    zone = ZoneInfo("Australia/Melbourne")
    assert start.astimezone(zone).hour == end.astimezone(zone).hour == 0
    assert end - start == timedelta(days=15, hours=-1)


def test_miclub_requests_both_fee_groups_through_day_fourteen():
    now = datetime(2026, 10, 16, 1, tzinfo=timezone.utc)
    requests = list(MiClubSpider(now=now).iter_requests())
    assert len(requests) == 30
    assert sum("selectedDate=2026-10-30" in request.url for request in requests) == 2
    assert not any("selectedDate=2026-10-31" in request.url for request in requests)


def test_window_rejects_naive_now():
    with pytest.raises(ValueError, match="timezone-aware"):
        scrape_window("Australia/Melbourne", datetime(2026, 10, 16))
