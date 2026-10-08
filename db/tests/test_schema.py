from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from golfdb.models import Course, TeeTime


def test_tables_constraints_and_index(engine):
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) >= {"courses", "tee_times", "scrape_runs"}

    tee_uniques = {tuple(item["column_names"]) for item in inspector.get_unique_constraints("tee_times")}
    assert ("course_id", "starts_at", "holes") in tee_uniques

    index_names = {item["name"] for item in inspector.get_indexes("tee_times")}
    assert "ix_tee_times_starts_at_course_id" in index_names

    starts_at = next(col for col in inspector.get_columns("tee_times") if col["name"] == "starts_at")
    assert starts_at["type"].timezone is True


def test_unique_tee_time_slot(db_session):
    course = _course()
    db_session.add(course)
    db_session.flush()
    db_session.add(_tee_time(course.id))
    db_session.flush()
    db_session.add(_tee_time(course.id))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_negative_price_rejected(db_session):
    course = _course()
    db_session.add(course)
    db_session.flush()
    slot = _tee_time(course.id)
    slot.price_per_player = Decimal("-1.00")
    db_session.add(slot)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_price_unit_defaults_to_per_round(db_session):
    course = _course()
    db_session.add(course)
    db_session.flush()
    db_session.execute(
        text(
            """
            INSERT INTO tee_times
                (course_id, starts_at, holes, spots_available, price_per_player, currency, booking_url, scraped_at)
            VALUES
                (:course_id, :starts_at, 18, 2, 40.00, 'USD', 'https://example.invalid/book', :scraped_at)
            """
        ),
        {
            "course_id": course.id,
            "starts_at": datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc),
            "scraped_at": datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc),
        },
    )
    price_unit = db_session.scalar(text("SELECT price_unit FROM tee_times WHERE course_id = :id"), {"id": course.id})
    assert price_unit == "per_round"


def _course() -> Course:
    return Course(
        slug="schema-probe",
        name="Schema Probe",
        holes_options=[18],
        platform="example_platform",
        timezone="America/Los_Angeles",
    )


def _tee_time(course_id: int) -> TeeTime:
    return TeeTime(
        course_id=course_id,
        starts_at=datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc),
        holes=18,
        spots_available=4,
        price_per_player=Decimal("55.00"),
        currency="USD",
        booking_url="https://example.invalid/book",
        scraped_at=datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc),
    )
