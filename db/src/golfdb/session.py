import os
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from golfdb.catalog import repo_root

DEFAULT_DATABASE_URL = "postgresql+psycopg://golf:golf@localhost:5432/teetimes"


def load_local_env(path: Path | None = None) -> None:
    """Load repo-root `.env` without overriding variables already set in the process."""
    if path is None:
        try:
            env_path = repo_root() / ".env"
        except RuntimeError:
            return
    else:
        env_path = path
    if not env_path.is_file():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def database_url() -> str:
    load_local_env()
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_engine(url: str | None = None) -> Engine:
    return create_engine(url or database_url(), pool_pre_ping=True)


def session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or get_engine())
