"""Run every spider in its own process.

One spider failing does not stop the others. A cron entry can call this every
15 minutes. The same function can later be invoked by Celery beat or Prefect.
"""

import importlib
import logging
import pkgutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from scrapy import Spider

import golf_scraper.spiders as spiders_package

logger = logging.getLogger(__name__)


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


def run_spider(name: str) -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "scrapy", "crawl", name],
        cwd=scraper_root(),
        check=False,
    )
    return completed.returncode


def run_all(runner: Callable[[str], int] = run_spider) -> int:
    names = spider_names()
    if not names:
        logger.warning("no spiders found")
        return 1
    failed: list[str] = []
    for name in names:
        logger.info("starting spider %s", name)
        try:
            code = runner(name)
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


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(run_all())


if __name__ == "__main__":
    main()
