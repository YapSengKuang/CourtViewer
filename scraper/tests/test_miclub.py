from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from golf_scraper.spiders.miclub import fixture_path, parse_miclub_timesheet
from golfdb.catalog import load_catalog

NOW = datetime(2026, 10, 9, 1, 0, tzinfo=timezone.utc)
MELBOURNE = ZoneInfo("Australia/Melbourne")


def test_parser_reads_public_times_and_combines_tees():
    course = next(course for course in load_catalog().courses if course.id == "club-mandalay")
    items = parse_miclub_timesheet(
        fixture_path().read_text(),
        course,
        holes=18,
        booking_url="https://mandalay.miclub.com.au/guests/bookings/ViewPublicTimesheet.msp?selectedDate=2026-10-10",
        now=NOW,
    )
    assert len(items) == 13
    twilight = datetime(2026, 10, 10, 15, 45, tzinfo=MELBOURNE).astimezone(timezone.utc)
    slot = next(item for item in items if item["starts_at"] == twilight)
    assert slot["holes"] == 18
    assert slot["spots_available"] == 7
    assert Decimal(str(slot["price_per_player"])) == Decimal("65.00")
    assert slot["currency"] == "AUD"
    assert slot["price_unit"] == "per_round"
    assert slot["course_slug"] == "club-mandalay"
    assert all(Decimal(str(item["price_per_player"])) != Decimal("35.00") for item in items)
