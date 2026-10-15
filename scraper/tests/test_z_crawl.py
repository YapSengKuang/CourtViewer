import json
import os
import subprocess
import sys
from decimal import Decimal

from sqlalchemy import select

from golf_scraper.spiders.example_platform import fixture_path, parse_example_platform
from golf_scraper.window import scrape_window
from golfdb.catalog import EXAMPLE_PLATFORM, load_catalog
from golfdb.models import Course, ScrapeRun, TeeTime
from golfdb.session import session_factory


def test_crawl_writes_fixture_tee_times(postgres):
    factory = session_factory(postgres)
    courses = [course for course in load_catalog().courses if course.platform == EXAMPLE_PLATFORM]
    payload = json.loads(fixture_path().read_text())

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scrapy",
            "crawl",
            "example_platform",
            "-s",
            "DOWNLOAD_DELAY=0",
            "-s",
            "AUTOTHROTTLE_ENABLED=False",
            "-s",
            "LOG_LEVEL=INFO",
        ],
        cwd=fixture_path().parents[2],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "no live endpoint yet" in result.stderr + result.stdout

    with factory() as session:
        for spec in courses:
            course = session.scalar(select(Course).where(Course.slug == spec.id))
            health = session.scalar(select(ScrapeRun).where(ScrapeRun.course_id == course.id))
            # Historical rows outside the current window may be retained. Only
            # compare the snapshot published by this crawl, not prior runs.
            rows = list(session.scalars(select(TeeTime).where(
                TeeTime.course_id == course.id,
                TeeTime.scraped_at == select(TeeTime.scraped_at).where(
                    TeeTime.course_id == course.id
                ).order_by(TeeTime.scraped_at.desc()).limit(1).scalar_subquery(),
            )))
            assert rows, spec.id
            scraped_at = rows[0].scraped_at
            window_start, window_end = scrape_window(spec.timezone, scraped_at)
            assert all(window_start <= row.starts_at < window_end for row in rows)
            expected = parse_example_platform(payload, spec, now=scraped_at)
            assert len(rows) == len(expected) == health.last_item_count
            assert health.last_error is None
            assert health.last_success_at is not None
            got = {(row.starts_at, row.holes, row.price_per_player) for row in rows}
            want = {
                (item["starts_at"], item["holes"], Decimal(str(item["price_per_player"])))
                for item in expected
            }
            assert got == want
            assert all(row.booking_url == "https://example.invalid/todo-booking" for row in rows)
            assert all(row.price_unit == "per_round" for row in rows)
