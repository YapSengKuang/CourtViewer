from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from golf_scraper.run_all import collection_outcome
from golfdb.models import Course, ScrapeExecution, ScrapePartition
from golfdb.session import session_factory


def test_partial_collection_is_failure_even_after_zero_process_exit(postgres):
    factory = session_factory(postgres)
    name = f'outcome-{uuid4()}'
    now = datetime.now(timezone.utc)
    with factory() as session:
        session.add(ScrapeExecution(id=str(uuid4()), spider=name, started_at=now,
                                   finished_at=now, status='partial'))
        session.commit()
    assert collection_outcome(name, now - timedelta(seconds=1)) == 1
    assert collection_outcome(f'missing-{uuid4()}', now) == 1


def test_interrupted_worker_marks_pending_coverage_incomplete(postgres):
    factory = session_factory(postgres)
    name = f'interrupted-{uuid4()}'
    execution_id = str(uuid4())
    now = datetime.now(timezone.utc)
    with factory() as session:
        course = session.scalar(select(Course).limit(1))
        session.add(ScrapeExecution(id=execution_id, spider=name, started_at=now, status='running'))
        session.flush()
        session.add(ScrapePartition(execution_id=execution_id, course_id=course.id, key='test-outcome',
            window_start=now, window_end=now+timedelta(days=1), status='pending'))
        session.commit()
    assert collection_outcome(name, now, interrupted=True) == 1
    with factory() as session:
        assert session.get(ScrapeExecution, execution_id).status == 'interrupted'
        assert session.scalar(select(ScrapePartition.status).where(
            ScrapePartition.execution_id == execution_id)) == 'incomplete'


def test_complete_collection_returns_success(postgres):
    factory = session_factory(postgres)
    name = f'complete-{uuid4()}'
    now = datetime.now(timezone.utc)
    with factory() as session:
        session.add(ScrapeExecution(id=str(uuid4()), spider=name, started_at=now,
                                   finished_at=now, status='complete'))
        session.commit()
    assert collection_outcome(name, now) == 0
