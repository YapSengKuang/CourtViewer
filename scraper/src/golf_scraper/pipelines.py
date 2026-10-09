"""Validate TeeTimeItems and upsert them. Site-specific fields never reach this module."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from scrapy.exceptions import DropItem
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from golf_scraper.items import PRICE_UNIT_PER_ROUND
from golf_scraper.window import scrape_window
from golfdb.models import Course, ScrapeRun, TeeTime
from golfdb.session import get_engine, session_factory

logger = logging.getLogger(__name__)

EMPTY_RUN_ERROR = "no tee times returned"


def rejection_reason(item, *, now: datetime) -> str | None:
    """Return why this item should be dropped, or None if it can be stored."""
    starts_at = item.get("starts_at")
    if not isinstance(starts_at, datetime) or starts_at.tzinfo is None:
        return "missing start time"
    if starts_at < now:
        return "start time is in the past"
    price = item.get("price_per_player")
    if price is not None and Decimal(str(price)) < 0:
        return "negative price"
    return None


class TeeTimePipeline:
    def __init__(self):
        self.crawler = None

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        pipeline.crawler = crawler
        return pipeline

    def open_spider(self, spider=None):
        spider = self._spider(spider)
        self.started_at = getattr(spider, "run_started_at", None) or datetime.now(timezone.utc)
        self.slugs = [str(slug) for slug in getattr(spider, "course_slugs", [])]
        self.counts: dict[str, int] = {slug: 0 for slug in self.slugs}
        self.errors: dict[str, str] = {}
        self.engine = get_engine()
        self.session = session_factory(self.engine)()
        rows = self.session.scalars(select(Course).where(Course.slug.in_(self.slugs))).all()
        self.courses_by_slug = {course.slug: course for course in rows}

    def process_item(self, item, spider=None):
        slug = item.get("course_slug")
        slug_text = str(slug) if slug is not None else ""
        reason = rejection_reason(item, now=self.started_at)
        if reason:
            logger.warning("dropping tee time for %s: %s", slug_text or "?", reason)
            raise DropItem(reason)
        try:
            with self.session.begin_nested():
                self._upsert(item, slug_text)
        except DropItem:
            raise
        except Exception as exc:
            if slug_text:
                self.errors[slug_text] = str(exc)
            logger.exception("failed to store tee time for %s", slug_text or "?")
            raise
        self.counts[slug_text] = self.counts.get(slug_text, 0) + 1
        return item

    def close_spider(self, spider=None):
        spider = self._spider(spider)
        try:
            errors = dict(self.errors)
            for slug, message in getattr(spider, "course_errors", {}).items():
                errors[str(slug)] = message
            slugs = list(dict.fromkeys([*self.slugs, *self.counts, *errors]))
            for slug in slugs:
                course = self._course(slug)
                if course is None:
                    logger.error("no course row for slug %s; skipping health update", slug)
                    continue
                if slug in errors:
                    self._record(course, item_count=self.counts.get(slug, 0), error=errors[slug])
                    continue
                count = self.counts.get(slug, 0)
                if count < 1:
                    logger.warning(
                        "spider %s normally returns tee times but course %s returned 0 items; "
                        "leaving existing rows in place",
                        spider.name,
                        slug,
                    )
                    self._record(course, item_count=0, error=EMPTY_RUN_ERROR)
                    continue
                self._delete_stale(course)
                self._record(course, item_count=count, error=None, succeeded=True)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        finally:
            self.session.close()
            self.engine.dispose()

    def _spider(self, spider):
        if spider is not None:
            return spider
        if self.crawler is not None:
            return self.crawler.spider
        raise RuntimeError("tee time pipeline was closed without a spider")

    def _course(self, slug: str) -> Course | None:
        course = self.courses_by_slug.get(slug)
        if course is not None:
            return course
        course = self.session.scalar(select(Course).where(Course.slug == slug))
        if course is not None:
            self.courses_by_slug[slug] = course
        return course

    def _upsert(self, item, slug: str) -> None:
        course = self._course(slug)
        if course is None:
            raise DropItem(f"unknown course {slug}")
        price_unit = item.get("price_unit") or PRICE_UNIT_PER_ROUND
        statement = insert(TeeTime).values(
            course_id=course.id,
            starts_at=item["starts_at"],
            holes=int(item["holes"]),
            spots_available=int(item["spots_available"]),
            price_per_player=Decimal(str(item["price_per_player"])),
            currency=str(item["currency"]),
            price_unit=str(price_unit),
            booking_url=item["booking_url"],
            scraped_at=self.started_at,
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_tee_times_course_start_holes",
            set_={
                "spots_available": statement.excluded.spots_available,
                "price_per_player": statement.excluded.price_per_player,
                "currency": statement.excluded.currency,
                "price_unit": statement.excluded.price_unit,
                "booking_url": statement.excluded.booking_url,
                "scraped_at": statement.excluded.scraped_at,
            },
        )
        self.session.execute(statement)

    def _delete_stale(self, course: Course) -> None:
        window_start, window_end = scrape_window(course.timezone, self.started_at)
        self.session.execute(
            delete(TeeTime).where(
                TeeTime.course_id == course.id,
                TeeTime.starts_at >= window_start,
                TeeTime.starts_at < window_end,
                TeeTime.scraped_at < self.started_at,
            )
        )

    def _record(
        self,
        course: Course,
        *,
        item_count: int,
        error: str | None,
        succeeded: bool = False,
    ) -> None:
        run = course.scrape_run
        if run is None:
            run = ScrapeRun(course_id=course.id)
            self.session.add(run)
            course.scrape_run = run
        run.last_item_count = item_count
        if succeeded:
            run.last_success_at = datetime.now(timezone.utc)
            run.last_error = None
        elif error is not None:
            run.last_error = error
