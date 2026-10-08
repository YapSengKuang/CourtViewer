from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from golfdb.session import get_engine

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture(scope="session")
def engine():
    eng = get_engine()
    try:
        with eng.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.skip(f"Postgres is not available ({exc})")
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    return eng


@pytest.fixture
def db_session(engine):
    """Session bound to a transaction that rolls back when the test ends.

    join_transaction_mode="create_savepoint" lets code under test call commit()
    without leaving rows behind.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
