from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from golfdb.catalog import CourseCatalog, load_catalog
from golf_scraper.local import (
    PublicHttp, SameOriginRedirect, SourceUnavailable, collect, output_lock,
    read_report, save_report, seconds_until_next_check, validate_calendar, validate_course,
)
from golf_scraper.spiders.miclub import parse_miclub_timesheet

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / 'tests/fixtures/local'
NOW = datetime(2026, 11, 4, tzinfo=timezone.utc)


@pytest.fixture
def catalog():
    return load_catalog(ROOT / 'courses.local.yaml')


def calendar(course):
    groups = ''.join(f'<div class="feeGroupRow" data-feeid="{g["id"]}"></div>'
                     for g in course.params['fee_groups'])
    return f"<html><script>var bookingResourceId = '3000000'; var publicCaptchaEnabled = false;</script>{groups}</html>"


def blank():
    return {'schema_version': 1, 'courses': {}}


@pytest.mark.parametrize(('slug', 'group_index', 'fixture', 'prices'), [
    ('morack', 0, 'morack_sheet', {'27.00'}),
    ('morack', 0, 'morack_weekend', {'30.00'}),
    ('yarra-bend', 0, 'yarra18', {'55.00'}),
    ('yarra-bend', 1, 'yarra9', {'45.00'}),
    ('yarra-bend', 1, 'yarra9_friday', {'45.00', '49.00'}),
    ('yarra-bend', 0, 'yarra_weekend', {'62.00', '67.00'}),
])
def test_sanitised_live_source_fixtures(catalog, slug, group_index, fixture, prices):
    course = next(c for c in catalog.courses if c.id == slug)
    group = course.params['fee_groups'][group_index]
    params = {**course.params, **{k: v for k, v in group.items() if k.endswith('fee_labels') or k == 'fee_layout'}}
    items = parse_miclub_timesheet((FIXTURES / f'{fixture}.html').read_text(),
        course.model_copy(update={'params': params}), holes=group['holes'],
        booking_url=course.booking_url, now=NOW)
    assert items
    assert {i['price_per_player'] for i in items} <= prices
    assert all(1 <= i['spots_available'] <= 4 and i['holes'] == group['holes'] for i in items)
    assert len({i['source_slot_key'] for i in items}) == len(items)


@pytest.mark.parametrize(('slug', 'holes', 'day', 'price'), [
    ('northcote', 18, '2026-11-06', '34.75'),
    ('northcote', 9, '2026-11-06', '27.00'),
    ('northcote', 18, '2026-11-07', None),
    ('northcote', 9, '2026-11-07', '29.50'),
    ('bundoora-park', 18, '2026-11-06', '40.00'),
    ('bundoora-park', 9, '2026-11-06', '27.50'),
    ('bundoora-park', 18, '2026-11-07', '43.60'),
    ('bundoora-park', 9, '2026-11-07', '28.55'),
    ('growling-frog', 18, '2026-11-06', '69.00'),
    ('growling-frog', 9, '2026-11-06', '48.00'),
    ('growling-frog', 18, '2026-11-07', '69.00'),
    ('growling-frog', 9, '2026-11-07', '48.00'),
    ('melton-valley', 18, '2026-11-06', '40.00'),
    ('melton-valley', 9, '2026-11-06', '30.00'),
    ('melton-valley', 18, '2026-11-07', '49.00'),
    ('melton-valley', 9, '2026-11-07', '35.00'),
])
def test_alternative_courses_weekday_weekend_and_holes(catalog, slug, holes, day, price):
    course = next(c for c in catalog.courses if c.id == slug)
    group = next(g for g in course.params['fee_groups'] if g['holes'] == holes)
    params = {**course.params, **{k: v for k, v in group.items() if k.endswith('fee_labels') or k == 'fee_layout'}}
    html = (FIXTURES / f'{slug}-{day}-{holes}.html').read_text()
    items = parse_miclub_timesheet(html, course.model_copy(update={'params': params}),
        holes=holes, booking_url=course.booking_url, now=NOW)
    if price is None:
        assert items == []  # Verified unfiltered provider empty state.
    else:
        assert items and {i['price_per_player'] for i in items} == {price}
        assert all(i['holes'] == holes and 1 <= i['spots_available'] <= 4 for i in items)


@pytest.mark.parametrize(('old', 'new', 'error'), [
    ('data-html="true"', 'data-html="false"', 'popover'),
    ('data-content=', 'data-other=', 'popover'),
    ('fee-applied', 'unknown-fees', 'popover'),
    ('Adult - Online', 'Unverified Adult Offer', 'public adult price'),
    ('&lt;/ul&gt;', '&lt;li&gt;Adult - Online $70.00&lt;/li&gt;&lt;/ul&gt;', 'conflicting'),
])
def test_growling_popover_changes_fail_closed(catalog, old, new, error):
    course = next(c for c in catalog.courses if c.id == 'growling-frog')
    group = next(g for g in course.params['fee_groups'] if g['holes'] == 18)
    scoped = course.model_copy(update={'params': {**course.params, **group}})
    html = (FIXTURES / 'growling-frog-2026-11-06-18.html').read_text()
    assert old in html
    with pytest.raises(ValueError, match=error):
        parse_miclub_timesheet(html.replace(old, new), scoped, holes=18,
                              booking_url=course.booking_url, now=NOW)


def test_local_collector_scopes_popover_layout_to_growling_18_holes(catalog):
    course = next(c for c in catalog.courses if c.id == 'growling-frog')
    def fetch(url):
        if 'ViewPublicCalendar' in url:
            return calendar(course)
        holes = 18 if 'feeGroupId=101495' in url else 9
        return (FIXTURES / f'growling-frog-2026-11-06-{holes}.html').read_text()
    report = collect(CourseCatalog(courses=[course]), blank(), now=NOW,
        first_date=date(2026, 11, 6), days=1, fetch=fetch)
    result = report['courses']['growling-frog']
    assert result['status'] == 'complete'
    assert {p['tee_times'][0]['price_per_player'] for p in result['partitions'].values()} == {'69.00', '48.00'}


def test_enabled_alternatives_and_blocked_sources_have_explicit_access_states(catalog):
    assert {c.id for c in catalog.courses if c.params['collection_enabled']} == {
        'club-mandalay', 'morack', 'yarra-bend', 'northcote', 'bundoora-park',
        'growling-frog', 'melton-valley',
    }
    blocked = [c for c in catalog.courses if not c.params['collection_enabled']]
    def no_network(url):
        pytest.fail(f'disabled source contacted: {url}')
    report = collect(CourseCatalog(courses=blocked), blank(), now=NOW, days=1, fetch=no_network)
    assert len(report['courses']) == 5
    for course in blocked:
        result = report['courses'][course.id]
        assert result['status'] == course.params['local_status']
        assert 'partitions' not in result and 'last_success_at' not in result


def test_failure_keeps_prior_observation_and_does_not_claim_empty_or_new_success(catalog):
    course = next(c for c in catalog.courses if c.id == 'morack')
    selected = CourseCatalog(courses=[course])
    html = (FIXTURES / 'morack_sheet.html').read_text()
    calls = []
    def fetch(url):
        calls.append(url)
        return calendar(course) if 'ViewPublicCalendar' in url else html
    first = collect(selected, blank(), now=NOW, first_date=date(2026, 11, 5), days=1, fetch=fetch)
    result = first['courses']['morack']
    assert result['status'] == 'complete'
    old_partition = result['partitions']['2026-11-05:1115048']
    assert old_partition['tee_times']
    def failed(url):
        if 'ViewPublicCalendar' in url:
            return calendar(course)
        raise SourceUnavailable('changed source layout')
    second = collect(selected, first, now=NOW + timedelta(minutes=15),
                     first_date=date(2026, 11, 5), days=1, fetch=failed)
    current = second['courses']['morack']
    partition = current['partitions']['2026-11-05:1115048']
    assert current['status'] == partition['status'] == 'failed'
    assert current['last_success_at'] == result['last_success_at']
    assert partition['last_success_at'] == old_partition['last_success_at']
    assert partition['tee_times'] == old_partition['tee_times']
    assert first['courses']['morack']['status'] == 'complete'  # No mutation of caller data.
    # Repeated visits before the next interval do not contact the source.
    calls.clear()
    collect(selected, first, now=NOW + timedelta(minutes=14),
            first_date=date(2026, 11, 5), days=1, fetch=lambda url: calls.append(url))
    assert calls == []


def test_wrong_date_fails_only_that_partition_and_other_courses_continue(catalog):
    selected = CourseCatalog(courses=[c for c in catalog.courses if c.id in ('morack', 'yarra-bend')])
    courses = {c.params['base_url']: c for c in selected.courses}
    def fetch(url):
        course = next(c for origin, c in courses.items() if url.startswith(origin))
        if 'ViewPublicCalendar' in url:
            return calendar(course)
        if course.id == 'morack':
            return (FIXTURES / 'morack_weekend.html').read_text()  # Wrong date.
        return (FIXTURES / ('yarra9.html' if 'feeGroupId=993' in url else 'yarra18.html')).read_text()
    report = collect(selected, blank(), now=NOW, first_date=date(2026, 11, 5), days=1, fetch=fetch)
    assert report['courses']['morack']['status'] == 'failed'
    assert report['courses']['yarra-bend']['status'] == 'complete'
    assert 'tee_times' not in report['courses']['morack']['partitions']['2026-11-05:1115048']


def test_calendar_guard_rejects_captcha_missing_fee_and_wrong_resource(catalog):
    course = next(c for c in catalog.courses if c.id == 'morack')
    groups = validate_course(course)
    body = calendar(course)
    validate_calendar(body, course, groups)
    for changed in [body.replace('= false', '= true'), body.replace('1115048', '999'),
                    body.replace('3000000', '999'), body.replace('</html>', '')]:
        with pytest.raises(SourceUnavailable):
            validate_calendar(changed, course, groups)


def test_unknown_fee_cannot_be_treated_as_an_excluded_product(catalog):
    course = next(c for c in catalog.courses if c.id == 'morack')
    group = course.params['fee_groups'][0]
    params = {**course.params, **{k: v for k, v in group.items() if k.endswith('fee_labels')}}
    html = (FIXTURES / 'morack_sheet.html').read_text().replace('9 Holes Midweek', 'Unknown Adult Rate')
    with pytest.raises(ValueError, match='missing public adult price'):
        parse_miclub_timesheet(html, course.model_copy(update={'params': params}), holes=9,
                              booking_url=course.booking_url, now=NOW)


def test_only_verified_nonstandard_rates_can_prove_no_standard_offers(catalog):
    from parsel import Selector
    course = next(c for c in catalog.courses if c.id == 'morack')
    group = course.params['fee_groups'][0]
    params = {**course.params, **{k: v for k, v in group.items() if k.endswith('fee_labels')}}
    html = (FIXTURES / 'morack_sheet.html').read_text()
    for row in Selector(text=html).css('.row-time')[:2]:
        html = html.replace(row.get(), '')
    scoped = course.model_copy(update={'params': params})
    assert parse_miclub_timesheet(html, scoped, holes=9, booking_url=course.booking_url, now=NOW) == []
    with pytest.raises(ValueError, match='missing public adult price'):
        parse_miclub_timesheet(html.replace('Twilight Midweek', 'Unknown Rate'), scoped,
                              holes=9, booking_url=course.booking_url, now=NOW)


def test_restart_waits_for_saved_due_time_instead_of_another_full_interval(catalog):
    selected = CourseCatalog(courses=[c for c in catalog.courses if c.id == 'morack'])
    report = {'courses': {'morack': {'next_scheduled_at': (NOW + timedelta(minutes=15)).isoformat()}}}
    assert seconds_until_next_check(selected, report, NOW + timedelta(minutes=8)) == 7 * 60
    assert seconds_until_next_check(selected, report, NOW + timedelta(minutes=16)) == 0


def test_local_output_is_atomic_validated_and_locked(tmp_path):
    path = tmp_path / 'tee-times.json'
    assert read_report(path) == blank()
    with output_lock(path):
        with pytest.raises(ValueError, match='another local collector'):
            with output_lock(path):
                pytest.fail('overlap allowed')
        save_report(path, blank())
    assert read_report(path) == blank()
    path.write_text(json.dumps({'schema_version': 99, 'courses': {}}))
    with pytest.raises(ValueError, match='version 1'):
        read_report(path)


def test_robots_denial_and_unavailable_policy_never_fetch_tee_sheet(monkeypatch):
    client = PublicHttp()
    calls = []
    def read(url, delay=1):
        calls.append(url)
        return 'User-agent: *\nDisallow: /guests/'
    monkeypatch.setattr(client, '_read', read)
    with pytest.raises(SourceUnavailable, match='robots policy disallows'):
        client('https://course.example/guests/sheet')
    assert calls == ['https://course.example/robots.txt']
    def forbidden(url, delay=1):
        raise HTTPError(url, 403, 'Forbidden', None, None)
    monkeypatch.setattr(PublicHttp, '_read', lambda self, url, delay=1: forbidden(url, delay))
    with pytest.raises(SourceUnavailable, match='robots policy unavailable'):
        PublicHttp()('https://course.example/guests/sheet')


def test_transport_rejects_cross_origin_redirects_and_expired_budget():
    with pytest.raises(SourceUnavailable, match='cross-origin'):
        SameOriginRedirect().redirect_request(Request('https://course.example/sheet'),
            None, 302, 'redirect', {}, 'https://login.example/sheet')
    client = PublicHttp()
    client.deadline = 0
    with pytest.raises(SourceUnavailable, match='budget'):
        client._read('https://course.example/robots.txt')


@pytest.mark.parametrize('days', [0, 16])
def test_invalid_horizon_is_rejected_before_network(catalog, days):
    with pytest.raises(ValueError):
        collect(catalog, blank(), now=NOW, days=days)
