"""Publish the verified local collector's fresh observations into PostgreSQL.

Run once per scheduler invocation. No JSON import, local files or user-triggered
scraping. The existing database lock coordinates this and legacy collectors.
"""
from __future__ import annotations

import argparse
from datetime import datetime, time, timedelta, timezone
import logging
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from golfdb.catalog import CourseCatalog, load_catalog, repo_root
from golfdb.models import Course, ScrapeExecution, ScrapePartition
from golfdb.preflight import production_errors
from golfdb.session import get_engine
from golf_scraper.coverage import Coverage
from golf_scraper.local import collect, validate_course
from golf_scraper.pipelines import TeeTimePipeline
from golf_scraper.run_all import run_locked

logger = logging.getLogger(__name__)


def run_hosted(catalog: CourseCatalog, *, days: int = 15, workers: int = 3,
               now: datetime | None = None, fetch=None) -> int:
    """Caller must hold the global run lock; all database writes stay on this thread."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or not 1 <= days <= 15 or not 1 <= workers <= 3:
        raise ValueError('requires aware clock, 1-15 days and 1-3 workers')
    errors = production_errors(catalog)
    if errors:
        raise ValueError('; '.join(errors))
    for course in catalog.courses:
        if course.params.get('collection_enabled') is not True:
            raise ValueError(f'{course.id}: hosted catalog must contain only enabled courses')
        validate_course(course)  # Reject non-MiClub/daily sources before any requests.
        if int(course.params.get('refresh_interval_minutes', 15)) < 15:
            raise ValueError('hosted sources require a cadence of at least 15 minutes')
    engine = get_engine()
    try:
        with engine.connect() as connection:
            seeded = set(connection.scalars(select(Course.slug).where(
                Course.slug.in_([c.id for c in catalog.courses]))))
            if seeded != {c.id for c in catalog.courses}:
                raise ValueError('seed the complete hosted catalog before collection')
            attempts = dict(connection.execute(select(Course.slug, func.max(ScrapeExecution.started_at))
                .join(ScrapePartition, ScrapePartition.course_id == Course.id)
                .join(ScrapeExecution, ScrapeExecution.id == ScrapePartition.execution_id)
                .where(Course.slug.in_(list(seeded))).group_by(Course.slug)).all())
    finally:
        engine.dispose()
    due = CourseCatalog(courses=[c for c in catalog.courses if c.id not in attempts
        or now >= attempts[c.id] + timedelta(minutes=int(c.params.get('refresh_interval_minutes', 15)))])
    if not due.courses:
        logger.info('All courses are within their saved cooldown; no source requests.')
        return 0
    coverage = Coverage()
    for course in due.courses:
        zone = ZoneInfo(course.timezone)
        today = now.astimezone(zone).date()
        for offset in range(days):
            day = today + timedelta(days=offset)
            start = datetime.combine(day, time(), zone).astimezone(timezone.utc)
            end = datetime.combine(day + timedelta(days=1), time(), zone).astimezone(timezone.utc)
            for group in course.params['fee_groups']:
                coverage.expect(course.id, f"{day}:{group['id']}", start, end)
    spider = SimpleNamespace(name='hosted_public', course_slugs=[c.id for c in due.courses],
        coverage=coverage, run_started_at=now, course_errors={})
    pipeline = TeeTimePipeline()
    pipeline.open_spider(spider)  # Persist pending scopes before contacting providers.
    try:
        report = collect(due, {'schema_version': 1, 'courses': {}}, now=now,
                         days=days, workers=workers, fetch=fetch)
        for (slug, key), partition in coverage.partitions.items():
            entry = report['courses'][slug]
            result = entry.get('partitions', {}).get(key, {})
            if result.get('status') not in ('complete', 'empty'):
                coverage.fail(slug, key, result.get('error') or entry.get('error') or 'source unavailable')
                spider.course_errors[slug] = 'One or more requested sheets could not be verified.'
                continue
            for row in result['tee_times']:
                item = {**row, 'starts_at': datetime.fromisoformat(row['starts_at'])}
                # Local diagnostic timestamps are not database fields.
                item.pop('observed_at', None)
                pipeline.process_item(item, spider)
            coverage.complete(slug, key)
    except BaseException:
        for (slug, key), partition in coverage.partitions.items():
            coverage.fail(slug, key, 'collection interrupted before publication')
        raise
    finally:
        pipeline.close_spider(spider)
    good = sum(p.status in ('complete', 'empty') for p in coverage.partitions.values())
    logger.info('Published %s/%s verified date/fee scopes.', good, len(coverage.partitions))
    return 0 if good == len(coverage.partitions) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=repo_root() / 'scraper/courses.live.yaml')
    parser.add_argument('--days', type=int, default=15, choices=range(1, 16))
    parser.add_argument('--workers', type=int, default=3, choices=range(1, 4))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    try:
        catalog = load_catalog(args.catalog)
        code = run_locked(lambda: run_hosted(catalog, days=args.days, workers=args.workers))
    except Exception:
        logger.exception('Hosted collection failed')
        code = 1
    raise SystemExit(code)


if __name__ == '__main__':
    main()
