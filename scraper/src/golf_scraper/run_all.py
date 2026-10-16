"""Run every spider in its own process.

One spider failing does not stop the others. A cron entry can call this every
15 minutes. The same function can later be invoked by Celery beat or Prefect.
"""

import importlib
import logging
import pkgutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from scrapy import Spider
from sqlalchemy import Engine, text

from golfdb.session import get_engine

import golf_scraper.spiders as spiders_package

logger = logging.getLogger(__name__)

RUN_LOCK_KEY = 71920261016
RUN_BUDGET_SECONDS = 540
SPIDER_TIMEOUT_SECONDS = 120


def scraper_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "scrapy.cfg").is_file():
            return parent
    raise RuntimeError("could not find scrapy.cfg")


def spider_names() -> list[str]:
    names: list[str] = []
    for module_info in pkgutil.iter_modules(spiders_package.__path__):
        module = importlib.import_module(f"golf_scraper.spiders.{module_info.name}")
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and issubclass(value, Spider)
                and value is not Spider
                and value.name
                and not value.name.startswith("scrapy")
            ):
                names.append(value.name)
    return sorted(set(names))


def run_spider(name: str, timeout: float = SPIDER_TIMEOUT_SECONDS) -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "scrapy", "crawl", name],
        cwd=scraper_root(),
        check=False,
        timeout=timeout,
    )
    return completed.returncode


def run_all(runner: Callable[[str], int] | None = None) -> int:
    deadline = time.monotonic() + RUN_BUDGET_SECONDS
    names = spider_names()
    if not names:
        logger.warning("no spiders found")
        return 1
    failed: list[str] = []
    for name in names:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logger.error("scrape run deadline reached before %s", name)
            return 1
        logger.info("starting spider %s", name)
        try:
            code = runner(name) if runner is not None else run_spider(
                name, timeout=min(SPIDER_TIMEOUT_SECONDS, remaining)
            )
        except Exception:
            logger.exception("spider %s crashed", name)
            failed.append(name)
            continue
        if code != 0:
            logger.error("spider %s exited %s", name, code)
            failed.append(name)
    if failed:
        logger.error("spiders failed: %s", ", ".join(failed))
        return 1
    return 0


def run_locked(runner: Callable[[], int] = run_all, *, engine: Engine | None = None) -> int:
    """Hold a database session lock across the entire CLI run, across hosts.

    Exit 2 means another worker owns the lock. Failure to reach the database
    must fail closed rather than starting an unprotected collection run.
    """
    owns_engine = engine is None
    lock_engine = engine if engine is not None else get_engine()
    try:
        with lock_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": RUN_LOCK_KEY})
            if not acquired:
                logger.warning("another scraper run is active; skipping")
                return 2
            try:
                return runner()
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": RUN_LOCK_KEY})
    finally:
        if owns_engine:
            lock_engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        code = run_locked()
    except Exception:
        logger.exception("scrape run failed")
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
