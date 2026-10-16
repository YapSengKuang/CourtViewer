from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from golf_scraper.spiders.miclub import fixture_path, parse_miclub_timesheet
from golfdb.catalog import load_catalog

NOW = datetime(2026, 10, 9, 1, 0, tzinfo=timezone.utc)
MELBOURNE = ZoneInfo("Australia/Melbourne")


def test_parser_preserves_separate_starting_tees():
    course = next(course for course in load_catalog().courses if course.id == "club-mandalay")
    items = parse_miclub_timesheet(
        fixture_path().read_text(),
        course,
        holes=18,
        booking_url="https://mandalay.miclub.com.au/guests/bookings/ViewPublicTimesheet.msp?selectedDate=2026-10-10",
        now=NOW,
    )
    assert len(items) >= 13
    twilight = datetime(2026, 10, 10, 15, 45, tzinfo=MELBOURNE).astimezone(timezone.utc)
    twins = [item for item in items if item["starts_at"] == twilight]
    assert len(twins) == 2
    assert sorted(item["spots_available"] for item in twins) == [3, 4]
    assert len({item["source_slot_key"] for item in twins}) == 2
    slot = twins[0]
    assert slot["holes"] == 18
    assert slot["spots_available"] <= 4
    assert Decimal(str(slot["price_per_player"])) == Decimal("65.00")
    assert slot["currency"] == "AUD"
    assert slot["price_unit"] == "per_round"
    assert slot["course_slug"] == "club-mandalay"
    assert all(Decimal(str(item["price_per_player"])) != Decimal("35.00") for item in items)


def test_empty_and_sold_out_are_distinct_from_broken_pages():
    import pytest
    course = load_catalog().courses[0]
    def parse(body):
        return parse_miclub_timesheet(body, course, holes=18, booking_url='https://booking.example', now=NOW)
    assert parse('<html><script>var selectedDate = \'10-10-2026\'</script><div class="teetime-day-table"><p class="no-tee-times">No tee times available</p></div></html>') == []
    with pytest.raises(ValueError, match='no recognised rows'):
        parse('<html><script>var selectedDate = \'10-10-2026\'</script><div class="teetime-day-table"></div></html>')
    with pytest.raises(ValueError, match='incomplete'):
        parse(fixture_path().read_text().split('</html>')[0])
    sold_out = fixture_path().read_text().replace('cell-available', 'cell-taken')
    assert parse(sold_out) == []
    with pytest.raises(ValueError, match='unrecognised booking-cell'):
        parse(fixture_path().read_text().replace('cell-available', 'cell-changed'))


def test_response_for_wrong_date_fails_only_its_expected_partition():
    from scrapy.http import HtmlResponse
    from golf_scraper.spiders.miclub import MiClubSpider
    spider = MiClubSpider(now=NOW)
    request = next(spider.iter_requests())  # Requested 9 October; fixture is 10 October.
    response = HtmlResponse(request.url, request=request, body=fixture_path().read_bytes(), encoding='utf-8')
    assert list(spider.parse(response)) == []
    partition = spider.coverage.partitions[('club-mandalay', request.meta['partition_key'])]
    assert partition.status == 'failed'
    assert sum(p.status == 'pending' for p in spider.coverage.partitions.values()) == 29


def test_live_mandalay_empty_requires_unfiltered_provider_marker():
    import pytest
    from pathlib import Path
    course = next(c for c in load_catalog().courses if c.id == 'club-mandalay')
    html = (Path(__file__).parent / 'fixtures/mandalay_empty_timesheet.html').read_text()
    def parse(body):
        return parse_miclub_timesheet(body, course, holes=18, booking_url=course.booking_url, now=NOW)
    assert parse(html) == []
    for broken in (html.replace(' checked', ''),
                   html.replace('No rows meeting selected criteria.', 'Please sign in.'),
                   html.replace('teetime-day-table', 'unrelated-panel')):
        with pytest.raises(ValueError, match='no recognised rows'):
            parse(broken)


def test_morack_captured_midweek_sheet_keeps_standard_fee_only():
    from pathlib import Path
    course = next(c for c in load_catalog(Path(__file__).parents[1] / 'courses.beta.yaml').courses if c.id == 'morack')
    html = (Path(__file__).parent / 'fixtures/morack_timesheet.html').read_text()
    items = parse_miclub_timesheet(html, course, holes=9,
        booking_url=course.booking_url, now=datetime(2026, 10, 16, tzinfo=timezone.utc))
    assert items
    assert all(item['holes'] == 9 and Decimal(item['price_per_player']) == Decimal('27.00') for item in items)
    assert all(item['source_slot_key'] for item in items)


def test_morack_does_not_guess_unknown_standard_fee():
    import pytest
    from pathlib import Path
    course = next(c for c in load_catalog(Path(__file__).parents[1] / 'courses.beta.yaml').courses if c.id == 'morack')
    html = (Path(__file__).parent / 'fixtures/morack_timesheet.html').read_text().replace('9 Holes Midweek', 'Unverified Weekend Fee')
    with pytest.raises(ValueError, match='missing public adult price'):
        parse_miclub_timesheet(html, course, holes=9, booking_url=course.booking_url,
            now=datetime(2026, 10, 16, tzinfo=timezone.utc))
