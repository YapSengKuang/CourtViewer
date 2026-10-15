import json
from datetime import datetime, timezone
from decimal import Decimal

from golf_scraper.items import PRICE_UNIT_PER_ROUND
from golf_scraper.settings import (
    AUTOTHROTTLE_ENABLED,
    CONCURRENT_REQUESTS_PER_DOMAIN,
    DOWNLOAD_DELAY,
    DOWNLOAD_DELAY_JITTER,
    ROBOTSTXT_OBEY,
    USER_AGENT,
)
from golf_scraper.spiders.example_platform import (
    ExamplePlatformSpider,
    fixture_path,
    parse_example_platform,
)
from golf_scraper.window import scrape_window
from golfdb.catalog import load_catalog

NOW = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)


def test_polite_download_settings():
    assert ROBOTSTXT_OBEY is True
    assert DOWNLOAD_DELAY >= 1
    assert DOWNLOAD_DELAY_JITTER == 0
    assert CONCURRENT_REQUESTS_PER_DOMAIN == 1
    assert AUTOTHROTTLE_ENABLED is True
    assert "TeeTimeAggregator" in USER_AGENT


def test_parser_maps_fixture_into_utc_tee_times():
    course = _course("stub-north")
    items = parse_example_platform(_payload(), course, now=NOW)

    assert len(items) == 3
    assert {item["holes"] for item in items} == {9, 18}
    early_18 = next(item for item in items if item["holes"] == 18 and item["spots_available"] == 4)
    # 07:30 America/Los_Angeles on 2026-10-10 is 14:30 UTC (PDT, UTC-7).
    assert early_18["starts_at"] == datetime(2026, 10, 10, 14, 30, tzinfo=timezone.utc)
    assert early_18["course_slug"] == "stub-north"
    assert Decimal(str(early_18["price_per_player"])) == Decimal("72.00")
    assert early_18["currency"] == "USD"
    assert early_18["price_unit"] == PRICE_UNIT_PER_ROUND
    assert early_18["booking_url"] == "https://example.invalid/todo-booking"
    assert all(Decimal(str(item["price_per_player"])) != Decimal("70.00") for item in items)


def test_parser_keeps_only_holes_the_course_offers():
    nine_holes = parse_example_platform(_payload(), _course("stub-west"), now=NOW)
    eighteen_holes = parse_example_platform(_payload(), _course("stub-south"), now=NOW)
    assert [(item["holes"], item["spots_available"]) for item in nine_holes] == [(9, 2)]
    assert [item["holes"] for item in eighteen_holes] == [18, 18]


def test_parser_includes_day_fourteen_and_excludes_day_fifteen():
    course = _course("stub-north")
    payload = {
        "booking_url": "https://example.invalid/todo-booking",
        "slots": [
            _slot(offset_days=14, local_time="23:50"),
            _slot(offset_days=15, local_time="00:00"),
        ],
    }
    items = parse_example_platform(payload, course, now=NOW)
    assert len(items) == 1
    window_start, window_end = scrape_window(course.timezone, NOW)
    assert window_start <= items[0]["starts_at"] < window_end


def test_spider_covers_every_example_platform_course():
    spider = ExamplePlatformSpider(now=NOW)
    assert spider.course_slugs == ["stub-north", "stub-south", "stub-east", "stub-west"]


def _payload() -> dict:
    return json.loads(fixture_path().read_text())


def _course(slug: str):
    return next(course for course in load_catalog().courses if course.id == slug)


def _slot(*, offset_days: int, local_time: str) -> dict:
    return {
        "offset_days": offset_days,
        "local_time": local_time,
        "holes": 18,
        "spots": 1,
        "price_per_player": "50.00",
        "currency": "USD",
    }
