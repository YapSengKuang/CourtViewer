"""One agreed Freeway collection cycle per Melbourne calendar day, across hosts."""
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select

from golfdb.catalog import load_catalog
from golfdb.models import ScrapeExecution
from golfdb.session import get_engine
from golf_scraper.run_all import run_all, run_locked

MARKER = 'quick18_daily_attempt'


def collect_once(engine, runner=run_all, *, now=None):
    now = now or datetime.now(timezone.utc)
    zone = ZoneInfo('Australia/Melbourne')
    courses = load_catalog().courses
    if len(courses) != 1 or courses[0].id != 'freeway' or courses[0].platform != 'quick18':
        raise ValueError('daily Freeway runner requires the isolated Freeway catalog')
    if courses[0].params.get('collection_enabled') is not True:
        raise ValueError('Freeway collection is disabled')
    with engine.begin() as connection:
        last = connection.scalar(select(ScrapeExecution.started_at).where(
            ScrapeExecution.spider.in_([MARKER, 'quick18'])).order_by(ScrapeExecution.started_at.desc()).limit(1))
        if last and last.astimezone(zone).date() >= now.astimezone(zone).date():
            logging.info('Freeway already attempted this Melbourne date; no provider requests')
            return 0
        execution_id = str(uuid4())
        connection.execute(ScrapeExecution.__table__.insert().values(
            id=execution_id, spider=MARKER, started_at=now, status='running'))
    # The marker is committed before the worker starts. Failure or interruption
    # consumes today's attempt, so retries cannot exceed the agreed cadence.
    old = os.environ.get('FREEWAY_DAILY_ATTEMPT_ID')
    os.environ['FREEWAY_DAILY_ATTEMPT_ID'] = execution_id
    code = 1
    try:
        code = runner()
        return code
    finally:
        if old is None:
            os.environ.pop('FREEWAY_DAILY_ATTEMPT_ID', None)
        else:
            os.environ['FREEWAY_DAILY_ATTEMPT_ID'] = old
        with engine.begin() as connection:
            connection.execute(ScrapeExecution.__table__.update().where(ScrapeExecution.id == execution_id).values(
                finished_at=datetime.now(timezone.utc), status='complete' if code == 0 else 'failed'))


def main():
    logging.basicConfig(level=logging.INFO)
    engine = get_engine()
    try:
        raise SystemExit(run_locked(lambda: collect_once(engine), engine=engine))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
