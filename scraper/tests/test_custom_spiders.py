import json
from datetime import datetime, timezone
from decimal import Decimal

from golf_scraper.spiders.custom_stub_lake import fixture_path as lake_fixture
from golf_scraper.spiders.custom_stub_lake import parse_custom_stub_lake
from golf_scraper.spiders.custom_stub_ridge import fixture_path as ridge_fixture
from golf_scraper.spiders.custom_stub_ridge import parse_custom_stub_ridge
from golfdb.catalog import load_catalog

NOW = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)


def test_ridge_parser_reads_its_fixture():
    course = _course("stub-ridge")
    items = parse_custom_stub_ridge(json.loads(ridge_fixture().read_text()), course, now=NOW)
    assert [(item["holes"], item["spots_available"]) for item in items] == [(18, 3), (9, 2)]
    assert items[0]["starts_at"] == datetime(2026, 10, 11, 15, 10, tzinfo=timezone.utc)
    assert Decimal(str(items[0]["price_per_player"])) == Decimal("95.00")
    assert items[0]["booking_url"] == "https://example.invalid/todo-booking-ridge"
    assert items[0]["course_slug"] == "stub-ridge"
    assert items[0]["price_unit"] == "per_round"


def test_lake_parser_reads_its_fixture_and_skips_nine_holes():
    course = _course("stub-lake")
    items = parse_custom_stub_lake(json.loads(lake_fixture().read_text()), course, now=NOW)
    assert len(items) == 1
    assert items[0]["holes"] == 18
    assert items[0]["starts_at"] == datetime(2026, 10, 12, 18, 20, tzinfo=timezone.utc)
    assert Decimal(str(items[0]["price_per_player"])) == Decimal("110.00")
    assert items[0]["booking_url"] == "https://example.invalid/todo-booking-lake"
    assert items[0]["course_slug"] == "stub-lake"


def _course(slug: str):
    return next(course for course in load_catalog().courses if course.id == slug)
