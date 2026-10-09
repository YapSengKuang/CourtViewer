"""Stub spider for every course whose platform is example_platform.

The HTTP call is not implemented. start_requests feeds a checked-in fixture
through parse_example_platform so the pipeline can be exercised offline.
Replace that request once the real JSON endpoint is known. Do not guess a URL.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import scrapy

from golf_scraper.items import PRICE_UNIT_PER_ROUND, TeeTimeItem
from golf_scraper.window import scrape_window
from golfdb.catalog import EXAMPLE_PLATFORM, CourseSpec, load_catalog

# Not a booking endpoint. FixtureResponseMiddleware answers it locally.
FIXTURE_URL = "https://example.invalid/fixture/example-platform/{slug}"


def fixture_path() -> Path:
    name = "example_platform.json"
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "tests" / "fixtures" / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(name)


def parse_example_platform(
    payload: dict,
    course: CourseSpec,
    *,
    now: datetime,
) -> list[TeeTimeItem]:
    """Map one payload into TeeTimeItems for a single course.

    TODO: the field names below match the synthetic fixture, not a live API.
    When a real response is saved under tests/fixtures, change this mapping and
    keep the TeeTimeItem fields the same.
    """
    window_start, window_end = scrape_window(course.timezone, now)
    zone = ZoneInfo(course.timezone)
    local_today = now.astimezone(zone).date()
    default_booking_url = payload.get("booking_url")
    items: list[TeeTimeItem] = []

    for slot in payload.get("slots", []):
        holes = int(slot["holes"])
        if holes not in course.holes_options:
            continue
        local_day = local_today + timedelta(days=int(slot["offset_days"]))
        hour_text, minute_text = str(slot["local_time"]).split(":", 1)
        starts_at = datetime(
            local_day.year,
            local_day.month,
            local_day.day,
            int(hour_text),
            int(minute_text),
            tzinfo=zone,
        ).astimezone(timezone.utc)
        if not (window_start <= starts_at < window_end):
            continue
        items.append(
            TeeTimeItem(
                course_slug=course.id,
                starts_at=starts_at,
                holes=holes,
                spots_available=int(slot["spots"]),
                price_per_player=slot["price_per_player"],
                currency=slot["currency"],
                price_unit=slot.get("price_unit") or PRICE_UNIT_PER_ROUND,
                booking_url=slot.get("booking_url") or default_booking_url,
            )
        )
    return items


class ExamplePlatformSpider(scrapy.Spider):
    name = EXAMPLE_PLATFORM
    platform = EXAMPLE_PLATFORM

    def __init__(self, *args, **kwargs):
        now = kwargs.pop("now", None)
        super().__init__(*args, **kwargs)
        self.now = now if isinstance(now, datetime) else datetime.now(timezone.utc)
        self.run_started_at = self.now
        self.courses = [course for course in load_catalog().courses if course.platform == self.platform]
        self.course_slugs = [course.id for course in self.courses]
        self.course_errors: dict[str, str] = {}

    async def start(self):
        # Scrapy 2.13+ calls start(), not start_requests().
        for request in self.iter_requests():
            yield request

    def iter_requests(self):
        # TODO: request the platform JSON endpoint for each course, using
        # course.params (for example club_id) once those values are known.
        body = fixture_path().read_bytes()
        if not self.courses:
            self.logger.warning("no courses in courses.yaml use platform %s", self.platform)
        self.logger.warning(
            "%s has no live endpoint yet; parsing tests/fixtures/%s",
            self.name,
            fixture_path().name,
        )
        for course in self.courses:
            yield scrapy.Request(
                url=FIXTURE_URL.format(slug=course.id),
                callback=self.parse,
                errback=self.on_error,
                dont_filter=True,
                meta={"course": course, "fixture_body": body},
            )

    def parse(self, response):
        course: CourseSpec = response.meta["course"]
        try:
            payload = json.loads(response.text)
            items = parse_example_platform(payload, course, now=self.now)
        except Exception as exc:
            self.course_errors[course.id] = str(exc)
            self.logger.exception("failed to parse %s for %s", self.name, course.id)
            return
        if not items:
            self.logger.warning("%s parsed 0 tee times for %s", self.name, course.id)
        yield from items

    def on_error(self, failure):
        course: CourseSpec = failure.request.meta["course"]
        message = failure.getErrorMessage()
        self.course_errors[course.id] = message
        self.logger.error("%s request failed for %s: %s", self.name, course.id, message)
