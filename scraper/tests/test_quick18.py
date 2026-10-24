from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from parsel import Selector
from scrapy.http import HtmlResponse

from golfdb.catalog import load_catalog
from golf_scraper.spiders.quick18 import Quick18Spider, date_url, parse_matrix

DAY = date(2026, 10, 24)
NOW = datetime(2026, 10, 23, 13, tzinfo=timezone.utc)
CATALOG = Path(__file__).parents[1] / 'courses.freeway.yaml'
HTML = (Path(__file__).parent / 'fixtures/freeway_matrix.html').read_text()


@pytest.fixture
def course():
    return load_catalog(CATALOG).courses[0]


def test_captured_matrix_preserves_groups_standard_rates_and_local_date(course):
    items = parse_matrix(HTML, course, day=DAY, now=NOW)
    assert len(items) == 3
    assert {(i['holes'], i['price_per_player']) for i in items} == {(9, '34.00'), (18, '45.50')}
    assert [i['spots_available'] for i in items] == [2, 1, 1]
    assert items[0]['starts_at'] == datetime(2026, 10, 23, 19, 46, tzinfo=timezone.utc)
    assert len({i['source_slot_key'] for i in items}) == 3
    assert all(i['source_partition'] == DAY.isoformat() for i in items)
    assert all(i['currency'] == 'AUD' and i['price_unit'] == 'per_round' for i in items)


@pytest.mark.parametrize(('old', 'new', 'error'), [
    ('24/10/2026', '25/10/2026', 'date'),
    ('</html>', '', 'incomplete'),
    ('selected value="0"', 'selected value="2"', 'unfiltered'),
    ('selected value="Any"', 'selected value="Morning"', 'unfiltered'),
    ('1 or 2 players', '2 players', 'capacity'),
    ('1 or 2 players', '1 to 24 players', 'capacity'),
    ('$34.00', 'Call for price', 'price'),
    ('psid=10537', 'psid=99999', 'identity'),
    ('/teetimes/course/1599/', '/teetimes/course/8888/', 'group'),
    ('202610240646', '202610240647', 'time'),
    ('href="/teetimes/course/', 'href="https://untrusted.example/teetimes/course/', 'link'),
    ('Rate not available for date selected', 'Please log in', 'unavailable'),
    ('matrixTable', 'unknownTable', 'matrix'),
])
def test_changed_or_filtered_pages_fail_closed(course, old, new, error):
    assert old in HTML
    with pytest.raises(ValueError, match=error):
        parse_matrix(HTML.replace(old, new), course, day=DAY, now=NOW)


def test_unverified_empty_sheet_cannot_erase_availability(course):
    page = Selector(text=HTML)
    empty = HTML
    for row in page.css('tbody > tr'):
        empty = empty.replace(row.get(), '')
    with pytest.raises(ValueError, match='empty or unreleased'):
        parse_matrix(empty, course, day=DAY, now=NOW)


def test_past_offers_are_removed_and_conflicting_duplicates_rejected(course):
    assert parse_matrix(HTML, course, day=DAY, now=datetime(2026, 10, 24, 12, tzinfo=timezone.utc)) == []
    row = Selector(text=HTML).css('tbody > tr')[0].get()
    conflicting = HTML.replace('</tbody>', row.replace('$34.00', '$35.00') + '</tbody>')
    with pytest.raises(ValueError, match='conflicting duplicate'):
        parse_matrix(conflicting, course, day=DAY, now=NOW)


def test_same_time_on_different_starting_tees_does_not_combine_capacity(course):
    simultaneous = HTML.replace('8:38', '6:46').replace('202610240838', '202610240646')
    items = parse_matrix(simultaneous, course, day=DAY, now=NOW)
    nine_holes = [item for item in items if item['holes'] == 9]
    assert len(nine_holes) == 2
    assert nine_holes[0]['starts_at'] == nine_holes[1]['starts_at']
    assert sorted(item['spots_available'] for item in nine_holes) == [1, 2]
    assert nine_holes[0]['source_slot_key'] != nine_holes[1]['source_slot_key']


def test_date_links_strip_attribution_parameters(course):
    course.booking_url += '?utm_source=google&rwg_token=do-not-retain'
    assert date_url(course, date(2026, 10, 25)) == 'https://freeway.quick18.com/teetimes/searchmatrix?teedate=20261025'


def test_live_collection_is_disabled_and_robots_remains_enforced(monkeypatch):
    monkeypatch.setenv('COURSES_YAML', str(CATALOG))
    with pytest.raises(ValueError, match='disabled'):
        Quick18Spider(now=NOW)
    assert Quick18Spider.custom_settings == {'ROBOTSTXT_OBEY': True, 'ROBOTSTXT_USER_AGENT': 'Scrapy'}


def test_requests_and_parse_failures_are_isolated_by_date(monkeypatch, course):
    import golf_scraper.spiders.quick18 as module
    # In-memory test configuration only; the checked-in catalog stays disabled.
    course.params.update(collection_enabled=True, access_reference='offline-test-only')
    course.params.pop('access_mode', None)
    monkeypatch.setattr(module, 'load_catalog', lambda: type('Catalog', (), {'courses': [course]})())
    spider = Quick18Spider(now=NOW)
    requests = list(spider.iter_requests())
    assert len(requests) == 15
    assert requests[-1].meta['partition_key'] == '2026-11-07'
    response = HtmlResponse(requests[0].url, request=requests[0], body=HTML.encode(), encoding='utf-8')
    assert len(list(spider.parse(response))) == 3
    assert spider.coverage.partitions[('freeway', '2026-10-24')].status == 'complete'
    wrong_date = HtmlResponse(requests[1].url, request=requests[1], body=HTML.encode(), encoding='utf-8')
    assert list(spider.parse(wrong_date)) == []
    assert spider.coverage.partitions[('freeway', '2026-10-25')].status == 'failed'
    assert spider.coverage.partitions[('freeway', '2026-10-26')].status == 'pending'
