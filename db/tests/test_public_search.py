from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text, select
from sqlalchemy.exc import DBAPIError

from golfdb.models import Course, ScrapeRun, TeeTime


def search(session, day, **overrides):
    params = dict(day=day, start=time(0), end=time(23, 59, 59), players=2, holes=None, limit=100, offset=0)
    params.update(overrides)
    return session.scalar(text('''SELECT public.golf_search(
        :day, :start, :end, :players, :holes, :limit, :offset)'''), params)


@pytest.fixture
def availability(db_session):
    # Isolate from any previously seeded public catalog without deleting it.
    db_session.execute(text('UPDATE courses SET public_enabled = false'))
    course = Course(slug='rpc-probe', name='RPC Probe', timezone='Australia/Melbourne',
                    platform='miclub', holes_options=[9, 18], public_enabled=True)
    hidden = Course(slug='rpc-hidden', name='Hidden', timezone='Australia/Melbourne',
                    platform='miclub', holes_options=[18])
    db_session.add_all([course, hidden])
    db_session.flush()
    now = db_session.scalar(text('SELECT CURRENT_TIMESTAMP'))
    from zoneinfo import ZoneInfo
    day = now.astimezone(ZoneInfo(course.timezone)).date() + timedelta(days=14)
    start = datetime.combine(day, time(9), ZoneInfo(course.timezone)).astimezone(timezone.utc)
    for owner, clock, age, spots in [
        (course, start, 0, 4),
        (course, start + timedelta(hours=1), 61, 4),
        (course, start + timedelta(hours=2), 0, 1),
        (hidden, start, 0, 4),
        (course, now - timedelta(minutes=1), 0, 4),
    ]:
        db_session.add(TeeTime(course_id=owner.id, starts_at=clock, holes=18,
            spots_available=spots, price_per_player=Decimal('42.50'), currency='AUD',
            booking_url='https://booking.example/tee', scraped_at=now-timedelta(minutes=age)))
    db_session.add(ScrapeRun(course_id=course.id, last_error='secret internal connection details'))
    db_session.flush()
    return db_session, day


def test_rpc_filters_horizon_capacity_freshness_and_disabled_courses(availability):
    session, day = availability
    result = search(session, day)
    assert len(result['tee_times']) == 1
    slot = result['tee_times'][0]
    assert slot['course_slug'] == 'rpc-probe'
    assert slot['price_per_player'] == '42.50'
    assert slot['starts_at_local'].endswith('09:00:00')
    assert search(session, day, offset=1)['tee_times'] == []
    assert search(session, day, holes=9)['tee_times'] == []


@pytest.mark.parametrize('overrides', [
    {'players': 0}, {'players': 5}, {'players': None}, {'limit': 201}, {'limit': None},
    {'offset': -1}, {'offset': 10001}, {'holes': 8}, {'start': time(12), 'end': time(11)},
])
def test_rpc_rejects_unbounded_or_invalid_search(availability, overrides):
    session, day = availability
    with pytest.raises(DBAPIError, match='Invalid search parameters'):
        search(session, day, **overrides)


def test_rpc_rejects_day_fifteen(availability):
    session, day = availability
    with pytest.raises(DBAPIError, match='Date must be today through day'):
        search(session, day + timedelta(days=1))


def test_health_sanitises_errors_and_excludes_hidden_courses(availability):
    session, _ = availability
    health = session.scalar(text('SELECT public.golf_health()'))
    assert len(health['courses']) == 1
    assert health['courses'][0]['last_error'] == 'Source temporarily unavailable'
    assert 'secret' not in str(health)


def test_public_permissions_and_rls_are_closed_by_default(db_session):
    rows = db_session.execute(text('''
        SELECT relname, relrowsecurity FROM pg_class
        WHERE oid IN ('public.courses'::regclass, 'public.tee_times'::regclass, 'public.scrape_runs'::regclass)
    ''')).all()
    assert len(rows) == 3 and all(enabled for _, enabled in rows)
    # PUBLIC (grantee 0) must not inherit execute on these SECURITY DEFINER functions.
    grants = db_session.scalar(text('''
        SELECT count(*) FROM pg_proc p,
             LATERAL aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
        WHERE p.oid IN (
            'public.golf_search(date,time,time,integer,integer,integer,integer)'::regprocedure,
            'public.golf_health()'::regprocedure)
        AND a.grantee = 0 AND a.privilege_type = 'EXECUTE'
    '''))
    assert grants == 0


def test_freshness_boundary_is_inclusive(availability):
    session, day = availability
    session.execute(text('''UPDATE tee_times SET scraped_at = CURRENT_TIMESTAMP - interval '60 minutes'
        WHERE course_id = (SELECT id FROM courses WHERE slug = 'rpc-probe')
        AND scraped_at < CURRENT_TIMESTAMP - interval '60 minutes' '''))
    assert len(search(session, day)['tee_times']) == 2
    session.execute(text('''UPDATE tee_times SET scraped_at = scraped_at - interval '1 microsecond'
        WHERE scraped_at = CURRENT_TIMESTAMP - interval '60 minutes' '''))
    assert len(search(session, day)['tee_times']) == 1


def test_read_only_role_can_call_rpc_but_cannot_read_or_write_tables(availability):
    session, day = availability
    # Transactional role creation is rolled back with the test, including grants.
    session.execute(text('CREATE ROLE golf_rpc_test_reader NOLOGIN'))
    session.execute(text('GRANT USAGE ON SCHEMA public TO golf_rpc_test_reader'))
    session.execute(text('''GRANT EXECUTE ON FUNCTION
        public.golf_search(date,time,time,integer,integer,integer,integer), public.golf_health()
        TO golf_rpc_test_reader'''))
    session.execute(text('SET LOCAL ROLE golf_rpc_test_reader'))
    try:
        assert len(search(session, day)['tee_times']) == 1
        for sql in ['SELECT * FROM public.tee_times',
                    "UPDATE public.courses SET public_enabled = true",
                    'SELECT * FROM public.scrape_runs']:
            with pytest.raises(DBAPIError, match='permission denied'):
                with session.begin_nested():
                    session.execute(text(sql))
    finally:
        session.execute(text('RESET ROLE'))


def test_rpc_time_bounds_are_inclusive(availability):
    session, day = availability
    assert len(search(session, day, start=time(9), end=time(9))['tee_times']) == 1
    assert search(session, day, start=time(9, 0, 1))['tee_times'] == []


def test_rpc_excludes_slots_that_have_already_started(availability):
    session, _ = availability
    from zoneinfo import ZoneInfo
    today = session.scalar(text('SELECT CURRENT_TIMESTAMP')).astimezone(ZoneInfo('Australia/Melbourne')).date()
    assert search(session, today)['tee_times'] == []


def test_party_size_cannot_combine_independent_groups(availability):
    session, day = availability
    original = session.scalar(select(TeeTime).join(Course).where(
        Course.slug == 'rpc-probe', TeeTime.spots_available == 4,
        TeeTime.scraped_at == text('CURRENT_TIMESTAMP'), TeeTime.starts_at > text('CURRENT_TIMESTAMP')))
    original.spots_available = 2
    original.source_slot_key = 'first-tee'
    session.add(TeeTime(course_id=original.course_id, starts_at=original.starts_at, holes=18,
        spots_available=2, price_per_player=original.price_per_player, currency='AUD',
        booking_url=original.booking_url, scraped_at=original.scraped_at, source_slot_key='tenth-tee'))
    session.flush()
    result = search(session, day)
    assert len(result['tee_times']) == 2
    assert {slot['source_slot_key'] for slot in result['tee_times']} == {'first-tee', 'tenth-tee'}
    assert search(session, day, players=4)['tee_times'] == []


def beta_search(session, day, **overrides):
    params = dict(day=day, start=time(0), end=time(23, 59, 59), players=2, holes=None,
                  limit=100, offset=0, sort='starts_at', slug=None)
    params.update(overrides)
    return session.scalar(text('''SELECT public.golf_search_v2(
        :day, :start, :end, :players, :holes, :limit, :offset, :sort, :slug)'''), params)


def test_beta_sorting_pages_and_course_filter(availability):
    session, day = availability
    original = session.scalar(select(TeeTime).join(Course).where(
        Course.slug == 'rpc-probe', TeeTime.spots_available == 4,
        TeeTime.scraped_at == text('CURRENT_TIMESTAMP'), TeeTime.starts_at > text('CURRENT_TIMESTAMP')))
    session.add(TeeTime(course_id=original.course_id, starts_at=original.starts_at + timedelta(minutes=5),
        holes=18, spots_available=4, price_per_player=Decimal('10.00'), currency='AUD',
        booking_url=original.booking_url, scraped_at=original.scraped_at, source_slot_key='cheaper'))
    session.flush()
    first = beta_search(session, day, sort='price', limit=1, slug='rpc-probe')
    assert first['has_more'] is True
    assert first['tee_times'][0]['price_per_player'] == '10.00'
    second = beta_search(session, day, sort='price', limit=1, offset=1)
    assert second['has_more'] is False
    assert second['tee_times'][0]['price_per_player'] == '42.50'
    assert beta_search(session, day, limit=1)['tee_times'][0]['price_per_player'] == '42.50'
    assert first['coverage'][0]['status'] == 'unchecked'


@pytest.mark.parametrize('overrides', [{'sort': 'bad'}, {'slug': 'rpc-hidden'}])
def test_beta_rejects_disabled_course_and_bad_sort(availability, overrides):
    session, day = availability
    with pytest.raises(DBAPIError):
        beta_search(session, day, **overrides)


def test_beta_courses_hide_disabled_and_include_local_horizon(availability):
    session, day = availability
    courses = session.scalar(text('SELECT public.golf_courses()'))['courses']
    assert [c['slug'] for c in courses] == ['rpc-probe']
    assert courses[0]['date_to'] == day.isoformat()


def test_beta_coverage_distinguishes_partial_from_fresh_empty(availability):
    from uuid import uuid4
    from zoneinfo import ZoneInfo
    from golfdb.models import ScrapeExecution, ScrapePartition
    session, day = availability
    course_id = session.scalar(select(Course.id).where(Course.slug == 'rpc-probe'))
    now = session.scalar(text('SELECT CURRENT_TIMESTAMP'))
    execution_id = str(uuid4())
    session.add(ScrapeExecution(id=execution_id, spider='probe', status='partial', started_at=now))
    session.flush()
    start = datetime.combine(day, time(0), ZoneInfo('Australia/Melbourne'))
    for key, status in [('nine', 'empty'), ('eighteen', 'failed')]:
        session.add(ScrapePartition(execution_id=execution_id, course_id=course_id, key=key,
            window_start=start, window_end=start+timedelta(days=1), status=status))
    session.flush()
    coverage = beta_search(session, day)['coverage'][0]
    assert coverage['status'] == 'incomplete' and coverage['checked'] == 1 and coverage['expected'] == 2
    assert coverage['availability_status'] == 'unavailable'
    session.execute(text("UPDATE scrape_partitions SET status='empty' WHERE execution_id=:id"), {'id': execution_id})
    assert beta_search(session, day)['coverage'][0]['status'] == 'complete'
    assert beta_search(session, day)['coverage'][0]['availability_status'] == 'empty'
    session.execute(text("UPDATE scrape_executions SET started_at = CURRENT_TIMESTAMP - interval '61 minutes' WHERE id=:id"), {'id': execution_id})
    assert beta_search(session, day)['coverage'][0]['availability_status'] == 'stale'


def test_beta_rpc_defaults_do_not_grant_public_execution(db_session):
    assert db_session.scalar(text('''SELECT count(*) FROM pg_proc p,
        LATERAL aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
        WHERE p.proname IN ('golf_search_v2','golf_courses','golf_coverage')
        AND a.grantee = 0 AND a.privilege_type = 'EXECUTE' ''')) == 0
