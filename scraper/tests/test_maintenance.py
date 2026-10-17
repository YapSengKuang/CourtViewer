from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from golfdb.models import ScrapeExecution
from golf_scraper.maintenance import maintain


def test_retention_preserves_active_and_recent_executions(postgres):
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=31)
    ids = [str(uuid4()) for _ in range(3)]
    with postgres.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(ScrapeExecution.__table__.insert(), [
                dict(id=ids[0], spider='retention-test', started_at=old, finished_at=old, status='complete'),
                dict(id=ids[1], spider='retention-test', started_at=old, finished_at=None, status='running'),
                dict(id=ids[2], spider='retention-test', started_at=now, finished_at=now, status='complete'),
            ])
            maintain(connection, now=now)
            remaining = set(connection.scalars(select(ScrapeExecution.id).where(ScrapeExecution.id.in_(ids))))
            assert remaining == {ids[1], ids[2]}
        finally:
            transaction.rollback()


def test_size_guard_stops_before_any_cleanup():
    from golf_scraper.maintenance import MAX_DATABASE_BYTES
    class Oversized:
        def scalar(self, query):
            return MAX_DATABASE_BYTES
        def execute(self, query):
            pytest.fail('guard must stop before writes')
    with pytest.raises(RuntimeError, match='safety threshold'):
        maintain(Oversized())
