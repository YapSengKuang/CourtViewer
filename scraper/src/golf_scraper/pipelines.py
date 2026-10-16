"""Stage observations and atomically publish only explicitly complete partitions."""
import logging
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from uuid import uuid4

from scrapy.exceptions import DropItem
from scrapy import signals
from sqlalchemy import delete, select

from golf_scraper.coverage import Coverage
from golf_scraper.items import PRICE_UNIT_PER_ROUND
from golfdb.models import Course, ScrapeRun, TeeTime, ScrapeExecution, ScrapePartition
from golfdb.session import get_engine, session_factory

logger = logging.getLogger(__name__)
EMPTY_RUN_ERROR = "no verified complete partitions"
MAX_STAGED_ITEMS = 20000


def rejection_reason(item, *, now):
    starts = item.get('starts_at')
    if not isinstance(starts, datetime) or starts.tzinfo is None:
        return 'missing start time'
    if starts < now:
        return 'start time is in the past'
    try:
        price = Decimal(str(item.get('price_per_player')))
        if not price.is_finite():
            return 'invalid price'
        if price < 0:
            return 'negative price'
        for key in ('holes', 'spots_available'):
            value = item.get(key)
            if isinstance(value, bool) or not isinstance(value, int):
                return f'invalid {key}'
        if item['holes'] not in (9, 18) or item['spots_available'] < 0:
            return 'invalid holes or capacity'
        url = urlsplit(item.get('booking_url') or '')
        if url.scheme not in ('http', 'https') or not url.hostname:
            return 'invalid booking URL'
        currency = item.get('currency')
        if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isalpha() or not currency.isupper():
            return 'invalid currency'
        if item.get('price_unit', PRICE_UNIT_PER_ROUND) != PRICE_UNIT_PER_ROUND:
            return 'unsupported price unit'
    except (ValueError, TypeError, InvalidOperation):
        return 'invalid price or item'
    return None


class TeeTimePipeline:
    def __init__(self):
        self.crawler = None

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        pipeline.crawler = crawler
        crawler.signals.connect(pipeline._on_spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(pipeline._on_spider_error, signal=signals.spider_error)
        return pipeline

    def _on_spider_error(self, failure, response, spider):
        # Callback/start errors not explicitly handled by an adapter fail closed.
        self.unscoped_errors.add('*')

    def _on_spider_closed(self, spider, reason):
        self._closing_reason = reason
        self.close_spider(spider)

    def _spider(self, spider):
        if spider is not None:
            return spider
        return self.crawler.spider

    def open_spider(self, spider=None):
        spider = self._spider(spider)
        self.started_at = getattr(spider, 'run_started_at', None) or datetime.now(timezone.utc)
        self.slugs = list(getattr(spider, 'course_slugs', []))
        self.engine = get_engine()
        self.session = session_factory(self.engine)()
        self.courses = {c.slug: c for c in self.session.scalars(select(Course).where(Course.slug.in_(self.slugs)))}
        self.coverage = getattr(spider, 'coverage', Coverage())
        spider.coverage = self.coverage
        self.staged = defaultdict(dict)
        self.rejected = defaultdict(int)
        self.total = 0
        self.unscoped_errors = set()
        self.execution_id = str(uuid4())
        self.session.add(ScrapeExecution(id=self.execution_id, spider=spider.name,
            started_at=self.started_at, status='running'))
        self.session.commit()
        self.coverage.on_expect = self._register
        for partition in self.coverage.partitions.values():
            self._register(partition)

    def _register(self, p):
        course = self.courses.get(p.course_slug)
        if course is None:
            raise ValueError(f'unknown course {p.course_slug}')
        self.session.add(ScrapePartition(execution_id=self.execution_id, course_id=course.id,
            key=p.key, window_start=p.start, window_end=p.end, status='pending'))
        self.session.commit()  # Survives worker interruption before any response.

    def process_item(self, item, spider=None):
        slug = str(item.get('course_slug', ''))
        key = str(item.get('source_partition', 'window'))
        identity = (slug, key)
        partition = self.coverage.partitions.get(identity)
        if partition is None:
            self.unscoped_errors.add(slug if slug in self.courses else "*")
            raise DropItem('item has no expected coverage partition')
        reason = rejection_reason(item, now=self.started_at)
        if reason == 'start time is in the past':
            raise DropItem(reason)  # Expected on today's sheet, not a failed parse.
        if not reason and item['holes'] not in self.courses[slug].holes_options:
            reason = 'unsupported holes for course'
        starts = item.get('starts_at')
        if not reason and not partition.start <= starts < partition.end:
            reason = 'item outside expected partition'
        slot_key = str(item.get('source_slot_key', ''))
        if not reason and (len(slot_key) > 200 or self.total >= MAX_STAGED_ITEMS):
            reason = 'staging bounds exceeded'
        group = (starts, item.get('holes'), slot_key)
        values = dict(item)
        values['source_partition'] = key
        values['source_slot_key'] = slot_key
        prior = self.staged[identity].get(group)
        if not reason and prior is not None and prior != values:
            reason = 'conflicting duplicate bookable group'
        if reason:
            self.rejected[identity] += 1
            self.coverage.fail(slug, key, reason)
            raise DropItem(reason)
        if prior is None:
            self.total += 1
        self.staged[identity][group] = values
        return item

    def close_spider(self, spider=None):
        # Scrapy closes pipelines before it emits spider_closed(reason); its
        # finish_reason statistic is not yet set at pipeline close time.
        if self.crawler is not None and not hasattr(self, '_closing_reason'):
            return
        spider = self._spider(spider)
        statuses = []
        course_success = []
        try:
            # A close triggered by shutdown/time budget cannot prove completeness.
            finish_reason = getattr(self, '_closing_reason', 'finished')
            for p in self.coverage.partitions.values():
                if p.course_slug in self.unscoped_errors or '*' in self.unscoped_errors:
                    self.coverage.fail(p.course_slug, p.key, 'unexpected partition in response')
                if finish_reason not in (None, 'finished'):
                    self.coverage.fail(p.course_slug, p.key, f'crawl closed: {finish_reason}')
                try:
                    self._publish(p)
                except Exception as exc:
                    self.session.rollback()
                    p.status, p.error = 'failed', str(exc)
                    record = self._partition_row(p)
                    record.status, record.error = 'failed', str(exc)
                    self.session.commit()
                    logger.exception('partition publication failed for %s/%s', p.course_slug, p.key)
                statuses.append(p.status)
            for slug, course in self.courses.items():
                parts = [p for p in self.coverage.partitions.values() if p.course_slug == slug]
                all_good = bool(parts) and all(p.status in ('complete', 'empty') for p in parts)
                course_success.append(all_good)
                newer = self.session.scalar(select(ScrapePartition.id).join(ScrapeExecution).where(
                    ScrapePartition.course_id == course.id,
                    ScrapeExecution.started_at > self.started_at,
                    ScrapePartition.status.in_(['complete', 'empty'])).limit(1))
                if newer:
                    continue  # An older worker must not overwrite newer course health.
                run = self.session.scalar(select(ScrapeRun).where(ScrapeRun.course_id == course.id))
                if run is None:
                    run = ScrapeRun(course_id=course.id)
                    self.session.add(run)
                run.last_item_count = sum(len(self.staged[(slug, p.key)]) for p in parts if p.status in ('complete', 'empty'))
                if all_good:
                    run.last_success_at = datetime.now(timezone.utc)
                    run.last_error = None
                else:
                    run.last_error = getattr(spider, 'course_errors', {}).get(slug) or EMPTY_RUN_ERROR
                    logger.warning('%s: incomplete or failed collection', slug)
            execution = self.session.get(ScrapeExecution, self.execution_id)
            execution.finished_at = datetime.now(timezone.utc)
            success = statuses and all(course_success) and all(s in ('complete', 'empty') for s in statuses)
            execution.status = 'complete' if success else ('partial' if any(s in ('complete', 'empty') for s in statuses) else 'failed')
            self.session.commit()
            if self.crawler:
                self.crawler.stats.set_value('collection/status', execution.status)
        except Exception:
            self.session.rollback()
            raise
        finally:
            self.coverage.on_expect = None
            self.session.close()
            self.engine.dispose()

    def _partition_row(self, p):
        return self.session.scalar(select(ScrapePartition).where(
            ScrapePartition.execution_id == self.execution_id,
            ScrapePartition.course_id == self.courses[p.course_slug].id,
            ScrapePartition.key == p.key))

    def _publish(self, p):
        course = self.courses[p.course_slug]
        # Serialize publishers and prevent an older snapshot overwriting a newer one.
        self.session.execute(select(Course.id).where(Course.id == course.id).with_for_update())
        record = self._partition_row(p)
        values = list(self.staged[(p.course_slug, p.key)].values())
        record.accepted_count = len(values)
        record.rejected_count = self.rejected[(p.course_slug, p.key)]
        newer = self.session.scalar(select(ScrapePartition.id).join(ScrapeExecution).where(
            ScrapePartition.course_id == course.id, ScrapePartition.key == p.key,
            ScrapePartition.status.in_(['complete', 'empty']), ScrapeExecution.started_at > self.started_at).limit(1))
        if newer:
            p.status, p.error = 'superseded', 'newer snapshot already published'
        elif p.status == 'complete':
            # Delete + insert within one transaction. Failures roll back both operations.
            self.session.execute(delete(TeeTime).where(TeeTime.course_id == course.id,
                TeeTime.source_partition == p.key,
                TeeTime.starts_at >= p.start, TeeTime.starts_at < p.end))
            for item in values:
                self.session.add(TeeTime(course_id=course.id, starts_at=item['starts_at'], holes=item['holes'],
                    spots_available=item['spots_available'], price_per_player=Decimal(str(item['price_per_player'])),
                    currency=item['currency'], price_unit=item.get('price_unit') or PRICE_UNIT_PER_ROUND,
                    booking_url=item['booking_url'], scraped_at=self.started_at,
                    source_partition=p.key, source_slot_key=item['source_slot_key']))
            self.session.flush()
            p.status = 'complete' if values else 'empty'
        elif p.status == 'pending':
            p.status, p.error = 'incomplete', 'expected response did not complete'
        record.status, record.error = p.status, p.error
        self.session.commit()
