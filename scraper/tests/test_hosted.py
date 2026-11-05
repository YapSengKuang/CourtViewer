from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, select, func
from sqlalchemy.orm import Session

from golfdb.catalog import CourseCatalog, load_catalog
from golfdb.models import Course, ScrapeExecution, ScrapePartition, TeeTime
from golfdb.seed import apply_seed
from golf_scraper.hosted import run_hosted
from golf_scraper.local import SourceUnavailable

ROOT = Path(__file__).parents[1]


@pytest.fixture
def hosted_case(postgres):
    base = next(c for c in load_catalog(ROOT / 'courses.live.yaml').courses if c.id == 'morack')
    course = base.model_copy(update={'id': 'hosted-' + uuid4().hex[:10]})
    with Session(postgres) as session:
        apply_seed(session, [course])
        session.commit()
        course_id = session.scalar(select(Course.id).where(Course.slug == course.id))
    now = datetime.now(ZoneInfo(course.timezone)).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    try:
        yield postgres, CourseCatalog(courses=[course]), course_id, now
    finally:
        with Session(postgres) as session:
            executions = session.scalars(select(ScrapePartition.execution_id).where(ScrapePartition.course_id == course_id)).all()
            session.execute(delete(Course).where(Course.id == course_id))
            session.execute(delete(ScrapeExecution).where(ScrapeExecution.id.in_(executions)))
            session.commit()


def fetcher(course, *, empty=False):
    def fetch(url):
        if 'ViewPublicCalendar' in url:
            return "<html><script>var bookingResourceId = '3000000';</script><div class='feeGroupRow' data-feeid='1115048'></div></html>"
        day = datetime.fromisoformat(parse_qs(urlsplit(url).query)['selectedDate'][0])
        if empty:
            return f"<html><script>var selectedDate = '{day:%d-%m-%Y}';</script><div class='teetime-day-table'><p class='no-tee-times'>No tee times available</p></div></html>"
        html = (ROOT / 'tests/fixtures/local/morack_sheet.html').read_text()
        return re.sub(r"var selectedDate = '[^']+'", f"var selectedDate = '{day:%d-%m-%Y}'", html)
    return fetch


def test_hosted_registers_before_network_publishes_and_honours_db_cooldown(hosted_case):
    engine, catalog, course_id, now = hosted_case
    fetch = fetcher(catalog.courses[0])
    def inspect(url):
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(ScrapePartition).where(
                ScrapePartition.course_id == course_id, ScrapePartition.status == 'pending')) == 2
        return fetch(url)
    assert run_hosted(catalog, now=now, days=2, fetch=inspect) == 0
    with Session(engine) as session:
        rows = session.scalars(select(TeeTime).where(TeeTime.course_id == course_id)).all()
        assert rows and all(row.scraped_at == now for row in rows)
        assert len({row.source_partition for row in rows}) == 2
        assert set(session.scalars(select(ScrapePartition.status).where(ScrapePartition.course_id == course_id))) == {'complete'}
        assert not session.get(Course, course_id).public_enabled
    assert run_hosted(catalog, now=now + timedelta(minutes=14), days=2,
                      fetch=lambda url: pytest.fail('cooldown contacted source')) == 0


def test_hosted_failure_preserves_observations_and_verified_empty_clears_them(hosted_case):
    engine, catalog, course_id, now = hosted_case
    assert run_hosted(catalog, now=now, days=1, fetch=fetcher(catalog.courses[0])) == 0
    with Session(engine) as session:
        before = [(r.source_slot_key, r.scraped_at) for r in session.scalars(select(TeeTime).where(TeeTime.course_id == course_id))]
    assert before
    def failed(url):
        raise SourceUnavailable('source unavailable')
    assert run_hosted(catalog, now=now + timedelta(minutes=15), days=1, fetch=failed) == 1
    with Session(engine) as session:
        after = [(r.source_slot_key, r.scraped_at) for r in session.scalars(select(TeeTime).where(TeeTime.course_id == course_id))]
        assert before == after
        assert 'failed' in set(session.scalars(select(ScrapePartition.status).where(ScrapePartition.course_id == course_id)))
    assert run_hosted(catalog, now=now + timedelta(minutes=30), days=1, fetch=fetcher(catalog.courses[0], empty=True)) == 0
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(TeeTime).where(TeeTime.course_id == course_id)) == 0
        assert 'empty' in set(session.scalars(select(ScrapePartition.status).where(ScrapePartition.course_id == course_id)))


def test_hosted_catalog_excludes_disabled_and_daily_sources():
    catalog = load_catalog(ROOT / 'courses.live.yaml')
    assert len(catalog.courses) == 7
    assert 'freeway' not in {c.id for c in catalog.courses}
    assert all(c.params['collection_enabled'] and c.platform == 'miclub' for c in catalog.courses)
