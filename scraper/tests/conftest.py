from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from golfdb.catalog import load_catalog
from golfdb.seed import apply_seed
from golfdb.session import get_engine, session_factory

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_ROOT / "db" / "alembic.ini"


@pytest.fixture(scope="session")
def postgres():
    engine = get_engine()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.skip(f"Postgres is not available ({exc})")
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    factory = session_factory(engine)
    with factory() as session:
        apply_seed(session, load_catalog().courses)
        session.commit()
    return engine
