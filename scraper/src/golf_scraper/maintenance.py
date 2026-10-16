"""Bound derived-cache growth before scheduled collection; never migrate here."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import Connection, delete, text

from golfdb.models import ScrapeExecution, TeeTime
from golfdb.session import get_engine

MAX_DATABASE_BYTES = 350 * 1024 * 1024


def maintain(connection: Connection, *, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    size = connection.scalar(text('SELECT pg_database_size(current_database())'))
    if size >= MAX_DATABASE_BYTES:
        raise RuntimeError('database safety threshold reached; collection is stopped')
    slots = connection.execute(delete(TeeTime).where(TeeTime.starts_at < now)).rowcount
    # Do not delete pending/interrupted runs automatically. Only terminal runs
    # with an explicit finish timestamp qualify; partitions cascade with them.
    executions = connection.execute(delete(ScrapeExecution).where(
        ScrapeExecution.status.in_(['complete', 'partial', 'failed']),
        ScrapeExecution.finished_at < now - timedelta(days=30),
    )).rowcount
    return {'database_bytes': size, 'expired_slots': slots, 'old_executions': executions}


def main() -> None:
    engine = get_engine()
    try:
        with engine.begin() as connection:
            result = maintain(connection)
        print(result)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
