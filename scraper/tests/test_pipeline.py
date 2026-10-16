import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from scrapy.exceptions import DropItem
from sqlalchemy import delete, select

from golf_scraper.items import TeeTimeItem
from golf_scraper.pipelines import EMPTY_RUN_ERROR, TeeTimePipeline
from golfdb.models import Course, ScrapeRun, TeeTime, ScrapeExecution, ScrapePartition
from golf_scraper.coverage import Coverage
from golf_scraper.window import scrape_window
from golfdb.session import session_factory

@dataclass(frozen=True)
class StoredTeeTime:
    starts_at: datetime
    price_per_player: Decimal
    spots_available: int
    scraped_at: datetime
    price_unit: str


@dataclass(frozen=True)
class StoredHealth:
    last_success_at: datetime | None
    last_item_count: int | None
    last_error: str | None


T0 = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)
INSIDE = datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)
INSIDE_LATER = datetime(2026, 10, 12, 18, 10, tzinfo=timezone.utc)
OUTSIDE = datetime(2026, 11, 15, 18, 0, tzinfo=timezone.utc)
OLD_SCRAPE = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


class FakeSpider:
    name = "example_platform"

    def __init__(self, *, now: datetime, slugs: list[str] | None = None):
        self.run_started_at = now
        self.course_slugs = slugs if slugs is not None else ["stub-north"]
        self.course_errors: dict[str, str] = {}
        self.coverage = Coverage()
        for slug in self.course_slugs:
            self.coverage.expect(slug, 'window', *scrape_window('America/Los_Angeles', now))


@pytest.fixture
def north(postgres):
    factory = session_factory(postgres)
    course_id = _reset_north(factory)
    yield factory
    _reset_north(factory)
    assert course_id


def test_pipeline_upserts_and_drops_slots_missing_from_the_next_run(north):
    factory = north
    _insert_row(factory, starts_at=INSIDE, scraped_at=OLD_SCRAPE, price="10.00")
    _insert_row(factory, starts_at=OUTSIDE, scraped_at=OLD_SCRAPE, price="11.00")

    kept = _item(starts_at=INSIDE, price="55.00", spots=3)
    vanished = _item(starts_at=INSIDE_LATER, price="60.00", spots=2)
    _run(FakeSpider(now=T0), [kept, vanished])

    stored = _rows(factory)
    assert len(stored) == 3
    updated = next(row for row in stored if row.starts_at == INSIDE)
    assert updated.price_per_player == Decimal("55.00")
    assert updated.spots_available == 3
    assert updated.scraped_at == T0
    assert updated.price_unit == "per_round"
    assert any(row.starts_at == OUTSIDE for row in stored)

    _run(FakeSpider(now=T0 + timedelta(minutes=15)), [kept])
    remaining = _rows(factory)
    assert {row.starts_at for row in remaining} == {INSIDE, OUTSIDE}
    health = _health(factory)
    assert health.last_item_count == 1
    assert health.last_error is None
    assert health.last_success_at is not None


def test_pipeline_drops_invalid_items(north):
    factory = north
    spider = FakeSpider(now=T0)
    pipeline = TeeTimePipeline()
    pipeline.open_spider(spider)
    try:
        with pytest.raises(DropItem, match="missing start time"):
            pipeline.process_item(_item(starts_at=None), spider)
        with pytest.raises(DropItem, match="in the past"):
            pipeline.process_item(_item(starts_at=T0 - timedelta(minutes=1)), spider)
        with pytest.raises(DropItem, match="negative price"):
            pipeline.process_item(_item(starts_at=INSIDE, price="-1.00"), spider)
        pipeline.process_item(_item(starts_at=INSIDE, price="0.00"), spider)
    finally:
        pipeline.close_spider(spider)
    stored = _rows(factory)
    assert stored == []  # Invalid observations fail the entire staged partition.


def test_zero_items_keeps_existing_rows_and_warns(north, caplog):
    factory = north
    _run(FakeSpider(now=T0), [_item(starts_at=INSIDE)])
    success_at = _health(factory).last_success_at

    with caplog.at_level(logging.WARNING, logger="golf_scraper.pipelines"):
        _run(FakeSpider(now=T0 + timedelta(minutes=15)), [])

    assert [row.starts_at for row in _rows(factory)] == [INSIDE]
    health = _health(factory)
    assert health.last_success_at == success_at
    assert health.last_item_count == 0
    assert health.last_error == EMPTY_RUN_ERROR
    assert "incomplete or failed" in caplog.text


def test_error_does_not_delete_existing_rows(north):
    factory = north
    _insert_row(factory, starts_at=INSIDE, scraped_at=OLD_SCRAPE, price="10.00")
    spider = FakeSpider(now=T0)
    pipeline = TeeTimePipeline()
    pipeline.open_spider(spider)
    try:
        pipeline.process_item(_item(starts_at=INSIDE_LATER), spider)
        broken = _item(starts_at=INSIDE + timedelta(hours=1))
        broken["booking_url"] = None
        with pytest.raises(Exception):
            pipeline.process_item(broken, spider)
    finally:
        pipeline.close_spider(spider)

    remaining = {row.starts_at for row in _rows(factory)}
    assert INSIDE in remaining
    assert INSIDE_LATER not in remaining  # Partial observations are never published.
    health = _health(factory)
    assert health.last_success_at is None
    assert health.last_error


def _run(spider: FakeSpider, items: list[TeeTimeItem], *, complete: bool | None = None) -> None:
    pipeline = TeeTimePipeline()
    pipeline.open_spider(spider)
    try:
        for item in items:
            pipeline.process_item(item, spider)
        if complete is True or (complete is None and items):
            for partition in spider.coverage.partitions.values():
                spider.coverage.complete(partition.course_slug, partition.key)
    finally:
        pipeline.close_spider(spider)


def _item(*, starts_at: datetime | None, price: str = "55.00", spots: int = 4) -> TeeTimeItem:
    return TeeTimeItem(
        course_slug="stub-north",
        starts_at=starts_at,
        holes=18,
        spots_available=spots,
        price_per_player=price,
        currency="USD",
        price_unit="per_round",
        booking_url="https://example.invalid/todo-booking",
    )


def _insert_row(factory, *, starts_at: datetime, scraped_at: datetime, price: str) -> None:
    with factory() as session:
        course = session.scalar(select(Course).where(Course.slug == "stub-north"))
        session.add(
            TeeTime(
                course_id=course.id,
                starts_at=starts_at,
                holes=18,
                spots_available=1,
                price_per_player=Decimal(price),
                currency="USD",
                booking_url="https://example.invalid/old",
                scraped_at=scraped_at,
            )
        )
        session.commit()


def _rows(factory) -> list[StoredTeeTime]:
    with factory() as session:
        course = session.scalar(select(Course).where(Course.slug == "stub-north"))
        rows = session.scalars(
            select(TeeTime).where(TeeTime.course_id == course.id).order_by(TeeTime.starts_at)
        ).all()
        return [
            StoredTeeTime(
                starts_at=row.starts_at,
                price_per_player=row.price_per_player,
                spots_available=row.spots_available,
                scraped_at=row.scraped_at,
                price_unit=row.price_unit,
            )
            for row in rows
        ]


def _health(factory) -> StoredHealth:
    with factory() as session:
        course = session.scalar(select(Course).where(Course.slug == "stub-north"))
        run = session.scalar(select(ScrapeRun).where(ScrapeRun.course_id == course.id))
        return StoredHealth(
            last_success_at=run.last_success_at,
            last_item_count=run.last_item_count,
            last_error=run.last_error,
        )


def _reset_north(factory) -> int:
    with factory() as session:
        course = session.scalar(select(Course).where(Course.slug == "stub-north"))
        session.execute(delete(TeeTime).where(TeeTime.course_id == course.id))
        session.execute(delete(ScrapePartition).where(ScrapePartition.course_id == course.id))
        run = session.scalar(select(ScrapeRun).where(ScrapeRun.course_id == course.id))
        run.last_success_at = None
        run.last_item_count = None
        run.last_error = None
        session.commit()
        return course.id


def test_verified_empty_clears_only_covered_scope(north):
    _insert_row(north, starts_at=INSIDE, scraped_at=OLD_SCRAPE, price='10.00')
    _insert_row(north, starts_at=OUTSIDE, scraped_at=OLD_SCRAPE, price='11.00')
    _run(FakeSpider(now=T0), [], complete=True)
    assert [row.starts_at for row in _rows(north)] == [OUTSIDE]
    assert _health(north).last_error is None
    assert _health(north).last_success_at is not None
    with north() as session:
        result = session.scalars(select(ScrapePartition).where(ScrapePartition.key == 'window').order_by(ScrapePartition.id.desc())).first()
        assert result.status == 'empty' and result.accepted_count == 0


def test_separate_groups_survive_storage_and_idempotent_rerun(north):
    one, two = _item(starts_at=INSIDE, spots=2), _item(starts_at=INSIDE, spots=2)
    one['source_slot_key'], two['source_slot_key'] = 'first-tee', 'tenth-tee'
    _run(FakeSpider(now=T0), [one, two])
    _run(FakeSpider(now=T0 + timedelta(minutes=1)), [one, two])
    assert len(_rows(north)) == 2
    assert all(row.spots_available == 2 for row in _rows(north))


def test_partial_course_publishes_good_partition_and_preserves_failed_one(north):
    first = _item(starts_at=INSIDE)
    second = _item(starts_at=INSIDE_LATER)
    first['source_partition'], second['source_partition'] = 'sheet-a', 'sheet-b'

    def spider(now):
        result = FakeSpider(now=now)
        result.coverage = Coverage()
        for key in ('sheet-a', 'sheet-b'):
            result.coverage.expect('stub-north', key, *scrape_window('America/Los_Angeles', now))
        return result

    _run(spider(T0), [first, second])
    later = spider(T0 + timedelta(minutes=1))
    later.coverage.complete('stub-north', 'sheet-a')
    later.coverage.fail('stub-north', 'sheet-b', 'HTTP failure')
    _run(later, [], complete=False)
    rows = _rows(north)
    assert len(rows) == 1 and rows[0].starts_at == INSIDE_LATER
    assert rows[0].scraped_at == T0
    assert _health(north).last_error
    with north() as session:
        execution = session.scalars(select(ScrapeExecution).where(
            ScrapeExecution.spider == 'example_platform',
            ScrapeExecution.started_at == later.run_started_at).order_by(ScrapeExecution.finished_at.desc())).first()
        assert execution.status == 'partial'


def test_older_snapshot_cannot_overwrite_newer_verified_empty(north):
    _run(FakeSpider(now=T0 + timedelta(minutes=2)), [], complete=True)
    _run(FakeSpider(now=T0), [_item(starts_at=INSIDE)])
    assert _rows(north) == []


def test_publication_failure_rolls_back_deleted_rows(north, monkeypatch):
    _insert_row(north, starts_at=INSIDE, scraped_at=OLD_SCRAPE, price='10.00')
    spider = FakeSpider(now=T0)
    pipeline = TeeTimePipeline()
    pipeline.open_spider(spider)
    pipeline.process_item(_item(starts_at=INSIDE_LATER), spider)
    spider.coverage.complete('stub-north', 'window')
    original_flush = pipeline.session.flush

    def fail_insert(*args, **kwargs):
        if any(isinstance(row, TeeTime) for row in pipeline.session.new):
            raise RuntimeError('injected publication failure')
        return original_flush(*args, **kwargs)

    monkeypatch.setattr(pipeline.session, 'flush', fail_insert)
    pipeline.close_spider(spider)
    rows = _rows(north)
    assert len(rows) == 1 and rows[0].starts_at == INSIDE
    assert rows[0].scraped_at == OLD_SCRAPE
    assert _health(north).last_error


def test_missing_response_persists_pending_then_incomplete_outcome(north):
    spider = FakeSpider(now=T0)
    pipeline = TeeTimePipeline()
    pipeline.open_spider(spider)
    with north() as session:
        record = session.scalar(select(ScrapePartition).where(ScrapePartition.execution_id == pipeline.execution_id))
        assert record.status == 'pending'
    pipeline.close_spider(spider)
    with north() as session:
        record = session.scalar(select(ScrapePartition).where(ScrapePartition.execution_id == pipeline.execution_id))
        assert record.status == 'incomplete'
        assert session.get(ScrapeExecution, pipeline.execution_id).status == 'failed'


def test_conflicting_duplicate_fails_partition_without_publishing(north):
    _insert_row(north, starts_at=INSIDE, scraped_at=OLD_SCRAPE, price='10.00')
    spider = FakeSpider(now=T0)
    pipeline = TeeTimePipeline()
    pipeline.open_spider(spider)
    pipeline.process_item(_item(starts_at=INSIDE, spots=2), spider)
    with pytest.raises(DropItem, match='conflicting duplicate'):
        pipeline.process_item(_item(starts_at=INSIDE, spots=4), spider)
    spider.coverage.complete('stub-north', 'window')
    pipeline.close_spider(spider)
    assert _rows(north)[0].scraped_at == OLD_SCRAPE


def test_shutdown_does_not_publish_even_an_observed_complete_response(north):
    from types import SimpleNamespace
    spider = FakeSpider(now=T0)
    pipeline = TeeTimePipeline()
    pipeline.open_spider(spider)
    pipeline.process_item(_item(starts_at=INSIDE), spider)
    spider.coverage.complete('stub-north', 'window')
    pipeline.crawler = SimpleNamespace(stats=SimpleNamespace(set_value=lambda *args: None))
    pipeline._on_spider_closed(spider, 'shutdown')
    assert _rows(north) == []
