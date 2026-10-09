from sqlalchemy import delete, func, select

from golfdb.catalog import load_catalog
from golfdb.models import Course, ScrapeRun
from golfdb.seed import apply_seed


def test_seed_inserts_then_updates_without_clearing_health(db_session):
    catalog = load_catalog()
    slugs = [course.id for course in catalog.courses]
    # Remove any already-seeded rows inside this transaction so the insert
    # path is exercised. The fixture rolls the delete back.
    db_session.execute(delete(Course).where(Course.slug.in_(slugs)))
    db_session.commit()

    first = apply_seed(db_session, catalog.courses)
    db_session.commit()
    assert first.inserted == 7
    assert first.updated == 0

    courses = list(db_session.scalars(select(Course).where(Course.slug.in_(slugs)).order_by(Course.slug)))
    assert [course.slug for course in courses] == [
        "club-mandalay",
        "stub-east",
        "stub-lake",
        "stub-north",
        "stub-ridge",
        "stub-south",
        "stub-west",
    ]
    north = next(course for course in courses if course.slug == "stub-north")
    assert north.holes_options == [9, 18]
    assert north.booking_url is None
    assert north.platform == "example_platform"
    runs = list(db_session.scalars(select(ScrapeRun).join(Course).where(Course.slug.in_(slugs))))
    assert len(runs) == 7
    assert all(run.last_success_at is None for run in runs)

    north_run = db_session.scalar(select(ScrapeRun).where(ScrapeRun.course_id == north.id))
    north_run.last_item_count = 12
    north_run.last_error = "previous"
    db_session.commit()

    second = apply_seed(db_session, catalog.courses)
    db_session.commit()
    assert second.inserted == 0
    assert second.updated == 7
    db_session.refresh(north_run)
    assert north_run.last_item_count == 12
    assert north_run.last_error == "previous"
    assert db_session.scalar(select(func.count()).select_from(Course).where(Course.slug.in_(slugs))) == 7
    assert db_session.scalar(select(func.count()).select_from(ScrapeRun).join(Course).where(Course.slug.in_(slugs))) == 7
