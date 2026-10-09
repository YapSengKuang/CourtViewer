from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select

from golfdb.models import Course, ScrapeRun, TeeTime
from golfdb.session import session_factory

LA = ZoneInfo("America/Los_Angeles")
NY = ZoneInfo("America/New_York")
BOOKING = "https://example.invalid/api-test"
SEARCH = {
    "date": "2026-10-10",
    "time_from": "07:00",
    "time_to": "12:00",
    "holes": 18,
    "players": 2,
}


def test_search_uses_each_course_timezone_and_freshness(client, postgres, frozen_now):
    factory = session_factory(postgres)
    _set_timezone(factory, "stub-south", "America/New_York")
    try:
        _insert(
            factory,
            "stub-north",
            local=datetime(2026, 10, 10, 7, 30, tzinfo=LA),
            spots=4,
            price="72.00",
            scraped_at=frozen_now - timedelta(minutes=5),
        )
        _insert(
            factory,
            "stub-south",
            local=datetime(2026, 10, 10, 7, 30, tzinfo=NY),
            spots=2,
            price="40.00",
            scraped_at=frozen_now - timedelta(minutes=5),
        )
        _insert(
            factory,
            "stub-north",
            local=datetime(2026, 10, 10, 13, 0, tzinfo=LA),
            spots=4,
            price="80.00",
            scraped_at=frozen_now - timedelta(minutes=5),
        )
        _insert(
            factory,
            "stub-north",
            local=datetime(2026, 10, 10, 8, 0, tzinfo=LA),
            spots=1,
            price="55.00",
            scraped_at=frozen_now - timedelta(minutes=5),
        )
        _insert(
            factory,
            "stub-north",
            local=datetime(2026, 10, 10, 9, 0, tzinfo=LA),
            spots=4,
            price="60.00",
            holes=9,
            scraped_at=frozen_now - timedelta(minutes=5),
        )
        _insert(
            factory,
            "stub-north",
            local=datetime(2026, 10, 10, 10, 0, tzinfo=LA),
            spots=4,
            price="70.00",
            scraped_at=frozen_now - timedelta(minutes=61),
        )

        response = client.get("/api/tee-times", params=SEARCH)
        assert response.status_code == 200
        body = response.json()["tee_times"]
        # 07:30 in New York is earlier in UTC than 07:30 in Los Angeles.
        assert [row["course_name"] for row in body] == ["Stub Course South", "Stub Course North"]
        south, north = body
        assert _parsed(south["starts_at"]) == datetime(2026, 10, 10, 11, 30, tzinfo=timezone.utc)
        assert south["starts_at_local"].startswith("2026-10-10T07:30:00-04:00")
        assert _parsed(north["starts_at"]) == datetime(2026, 10, 10, 14, 30, tzinfo=timezone.utc)
        assert north["starts_at_local"].startswith("2026-10-10T07:30:00-07:00")
        assert north["timezone"] == "America/Los_Angeles"
        assert north["holes"] == 18
        assert north["spots_available"] == 4
        assert north["currency"] == "USD"
        assert Decimal(north["price_per_player"]) == Decimal("72.00")
        assert north["booking_url"] == BOOKING
        assert north["address"] is None

        by_price = client.get("/api/tee-times", params={**SEARCH, "sort": "price"})
        assert [Decimal(row["price_per_player"]) for row in by_price.json()["tee_times"]] == [
            Decimal("40.00"),
            Decimal("72.00"),
        ]
        assert north["course_slug"] == "stub-north"

        any_holes = {**SEARCH}
        del any_holes["holes"]
        mixed = client.get("/api/tee-times", params=any_holes)
        assert {(row["course_slug"], row["holes"]) for row in mixed.json()["tee_times"]} == {
            ("stub-south", 18),
            ("stub-north", 18),
            ("stub-north", 9),
        }
    finally:
        _cleanup(factory)
        _set_timezone(factory, "stub-south", "America/Los_Angeles")


def test_search_rejects_a_backwards_time_window(client):
    response = client.get(
        "/api/tee-times",
        params={**SEARCH, "time_from": "15:00", "time_to": "09:00"},
    )
    assert response.status_code == 422


def test_search_rejects_bad_holes_and_players():
    from fastapi.testclient import TestClient

    from tee_api.main import app

    with TestClient(app) as test_client:
        assert test_client.get("/api/tee-times", params={**SEARCH, "holes": 7}).status_code == 422
        assert test_client.get("/api/tee-times", params={**SEARCH, "players": 0}).status_code == 422
        assert test_client.get("/api/tee-times", params={**SEARCH, "sort": "distance"}).status_code == 422


def test_courses_and_health(client, postgres):
    factory = session_factory(postgres)
    success_at = datetime(2026, 10, 10, 17, 0, tzinfo=timezone.utc)
    previous = _get_health(factory, "stub-north")
    _set_health(factory, "stub-north", success_at=success_at, item_count=3, error=None)
    try:
        courses = client.get("/api/courses")
        assert courses.status_code == 200
        by_slug = {row["slug"]: row for row in courses.json()["courses"]}
        assert set(by_slug) >= {
            "stub-north",
            "stub-south",
            "stub-east",
            "stub-west",
            "stub-ridge",
            "stub-lake",
        }
        assert by_slug["stub-north"]["holes_options"] == [9, 18]
        assert by_slug["stub-north"]["timezone"] == "America/Los_Angeles"
        assert by_slug["stub-north"]["booking_url"] is None

        health = client.get("/api/health")
        assert health.status_code == 200
        north = next(row for row in health.json()["courses"] if row["slug"] == "stub-north")
        assert _parsed(north["last_success_at"]) == success_at
        assert north["last_item_count"] == 3
        assert north["name"] == "Stub Course North"
        assert north["last_error"] is None
    finally:
        _set_health(factory, "stub-north", **previous)


def _parsed(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _insert(
    factory,
    slug: str,
    *,
    local: datetime,
    spots: int,
    price: str,
    holes: int = 18,
    scraped_at: datetime,
) -> None:
    with factory() as session:
        course = session.scalar(select(Course).where(Course.slug == slug))
        session.add(
            TeeTime(
                course_id=course.id,
                starts_at=local.astimezone(timezone.utc),
                holes=holes,
                spots_available=spots,
                price_per_player=Decimal(price),
                currency="USD",
                booking_url=BOOKING,
                scraped_at=scraped_at,
            )
        )
        session.commit()


def _cleanup(factory) -> None:
    with factory() as session:
        session.execute(delete(TeeTime).where(TeeTime.booking_url == BOOKING))
        session.commit()


def _set_timezone(factory, slug: str, timezone_name: str) -> None:
    with factory() as session:
        course = session.scalar(select(Course).where(Course.slug == slug))
        course.timezone = timezone_name
        session.commit()


def _get_health(factory, slug: str) -> dict:
    with factory() as session:
        course = session.scalar(select(Course).where(Course.slug == slug))
        run = session.scalar(select(ScrapeRun).where(ScrapeRun.course_id == course.id))
        return {
            "success_at": run.last_success_at,
            "item_count": run.last_item_count,
            "error": run.last_error,
        }


def _set_health(factory, slug: str, *, success_at, item_count, error) -> None:
    with factory() as session:
        course = session.scalar(select(Course).where(Course.slug == slug))
        run = session.scalar(select(ScrapeRun).where(ScrapeRun.course_id == course.id))
        run.last_success_at = success_at
        run.last_item_count = item_count
        run.last_error = error
        session.commit()
