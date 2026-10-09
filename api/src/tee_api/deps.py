from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from golfdb.session import get_engine, session_factory

_engine = None


def get_now() -> datetime:
    return datetime.now(timezone.utc)


def get_session() -> Iterator[Session]:
    global _engine
    if _engine is None:
        _engine = get_engine()
    session = session_factory(_engine)()
    try:
        yield session
    finally:
        session.close()
