import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from scrapy.exceptions import DropItem
from sqlalchemy import delete, select

from golf_scraper.items import TeeTimeItem
from golf_scraper.pipelines import EMPTY_RUN_ERROR, TeeTimePipeline
from golfdb.models import Course, ScrapeRun, TeeTime
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
    assert len(stored) == 1
    assert stored[0].price_per_player == Decimal("0.00")


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
    assert "returned 0 items" in caplog.text


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
    assert INSIDE_LATER in remaining
    health = _health(factory)
    assert health.last_success_at is None
    assert health.last_error


def _run(spider: FakeSpider, items: list[TeeTimeItem]) -> None:
    pipeline = TeeTimePipeline()
    pipeline.open_spider(spider)
    try:
        for item in items:
            pipeline.process_item(item, spider)
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
        run = session.scalar(select(ScrapeRun).where(ScrapeRun.course_id == course.id))
        run.last_success_at = None
        run.last_item_count = None
        run.last_error = None
        session.commit()
        return course.id
