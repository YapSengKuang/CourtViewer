from datetime import datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select, text

from golfdb.models import Course, ScrapeExecution, ScrapePartition, TeeTime


def test_calendar_metadata_and_coverage_distinguish_holes_and_failed_scopes(db_session):
    session = db_session
    session.execute(text('UPDATE courses SET public_enabled = false'))
    course = Course(slug='calendar-probe', name='Calendar probe', platform='miclub',
                    timezone='Australia/Melbourne', holes_options=[9, 18], public_enabled=True)
    session.add(course)
    session.flush()
    now = session.scalar(text('SELECT CURRENT_TIMESTAMP'))
    day = now.astimezone(ZoneInfo(course.timezone)).date() + timedelta(days=1)
    start = datetime.combine(day, time(8), ZoneInfo(course.timezone))
    execution = ScrapeExecution(id=str(uuid4()), spider='test', started_at=now, finished_at=now, status='partial')
    session.add(execution)
    session.flush()
    for holes, state in [(9, 'empty'), (18, 'failed')]:
        session.add(ScrapePartition(execution_id=execution.id, course_id=course.id, key=f'{day}:{holes}',
            holes=holes, window_start=start.replace(hour=0), window_end=start.replace(hour=0) + timedelta(days=1), status=state))
    session.add(TeeTime(course_id=course.id, starts_at=start, holes=18, spots_available=4,
        price_per_player=40, currency='AUD', booking_url='https://example.com/book', scraped_at=now,
        source_partition=f'{day}:18', source_slot_key='one'))
    session.flush()
    args = {'day': day, 'holes': 9}
    query = text("SELECT public.golf_search_v3(:day, '00:00', '23:59', 2, :holes)")
    nine = session.scalar(query, args)
    assert nine['coverage'][0]['status'] == 'complete'
    assert nine['coverage'][0]['availability_status'] == 'empty'
    assert nine['coverage'][0]['expected'] == 1
    eighteen = session.scalar(query, {**args, 'holes': 18})
    assert eighteen['coverage'][0]['status'] == 'incomplete'
    assert eighteen['coverage'][0]['availability_status'] == 'unavailable'
    assert eighteen['tee_times'] == []  # Retained diagnostic rows do not look live.
    metadata = session.scalar(text('SELECT public.golf_courses()'))['courses'][0]
    assert metadata['holes_options'] == [9, 18]
    course.holes_options = [9]
    session.flush()
    assert session.scalar(query, {**args, 'holes': 18})['coverage'] == []


def test_pending_collection_preserves_last_verified_calendar_coverage(db_session):
    session = db_session
    session.execute(text('UPDATE courses SET public_enabled = false'))
    course = Course(slug='pending-probe', name='Pending probe', platform='miclub',
        timezone='Australia/Melbourne', holes_options=[9], public_enabled=True)
    session.add(course)
    session.flush()
    now = session.scalar(text('SELECT CURRENT_TIMESTAMP'))
    day = now.astimezone(ZoneInfo(course.timezone)).date() + timedelta(days=1)
    start = datetime.combine(day, time(), ZoneInfo(course.timezone))
    for state, age in [('empty', 15), ('pending', 0)]:
        execution = ScrapeExecution(id=str(uuid4()), spider='test', started_at=now-timedelta(minutes=age), status='running')
        session.add(execution)
        session.flush()
        session.add(ScrapePartition(execution_id=execution.id, course_id=course.id, holes=9,
            key=f'{day}:9', window_start=start, window_end=start+timedelta(days=1), status=state))
    session.flush()
    coverage = session.scalar(text('SELECT public.golf_round_coverage(:day,NULL,9)'), {'day': day})
    assert coverage[0]['status'] == 'complete'
    assert coverage[0]['availability_status'] == 'empty'
    assert datetime.fromisoformat(coverage[0]['observed_at']) == now-timedelta(minutes=15)
