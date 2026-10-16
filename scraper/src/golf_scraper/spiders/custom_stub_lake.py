"""Stub spider for the bespoke stub-lake booking site.

TODO: replace the fixture request with the real endpoint after inspecting the site.
Do not guess a URL. Module name uses underscores because stub-lake is not a
valid Python module name.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import scrapy

from golf_scraper.coverage import fixture_coverage

from golf_scraper.items import PRICE_UNIT_PER_ROUND, TeeTimeItem
from golf_scraper.window import scrape_window
from golfdb.catalog import CourseSpec, load_catalog

COURSE_SLUG = "stub-lake"
FIXTURE_URL = "https://example.invalid/fixture/custom-stub-lake"


def fixture_path() -> Path:
    name = "custom_stub_lake.json"
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "tests" / "fixtures" / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(name)


def parse_custom_stub_lake(payload: dict, course: CourseSpec, *, now: datetime) -> list[TeeTimeItem]:
    """Map the synthetic stub-lake payload into TeeTimeItems.

    TODO: field names match tests/fixtures/custom_stub_lake.json, not a live
    response. Replace this mapping when a real payload is saved there.
    """
    window_start, window_end = scrape_window(course.timezone, now)
    zone = ZoneInfo(course.timezone)
    local_today = now.astimezone(zone).date()
    default_booking_url = payload.get("link")
    items: list[TeeTimeItem] = []
    for row in payload.get("rows", []):
        holes = int(row["holes"])
        if holes not in course.holes_options:
            continue
        local_day = local_today + timedelta(days=int(row["in_days"]))
        hour_text, minute_text = str(row["starts"]).split(":", 1)
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
                spots_available=int(row["open_spots"]),
                price_per_player=row["amount"],
                currency=row["currency"],
                price_unit=row.get("price_unit") or PRICE_UNIT_PER_ROUND,
                booking_url=row.get("link") or default_booking_url,
            )
        )
    return items


class CustomStubLakeSpider(scrapy.Spider):
    name = "custom_stub_lake"

    def __init__(self, *args, **kwargs):
        now = kwargs.pop("now", None)
        super().__init__(*args, **kwargs)
        self.now = now if isinstance(now, datetime) else datetime.now(timezone.utc)
        self.run_started_at = self.now
        self.courses = [course for course in load_catalog().courses if course.id == COURSE_SLUG]
        self.course_slugs = [course.id for course in self.courses]
        self.course_errors: dict[str, str] = {}
        fixture_coverage(self)

    async def start(self):
        for request in self.iter_requests():
            yield request

    def iter_requests(self):
        # TODO: request this course's own booking endpoint using course.params.
        body = fixture_path().read_bytes()
        self.logger.warning("%s has no live endpoint yet; parsing %s", self.name, fixture_path().name)
        for course in self.courses:
            yield scrapy.Request(
                url=FIXTURE_URL,
                callback=self.parse,
                errback=self.on_error,
                dont_filter=True,
                meta={"course": course, "fixture_body": body},
            )

    def parse(self, response):
        course: CourseSpec = response.meta["course"]
        try:
            payload = json.loads(response.text)
            if not isinstance(payload.get("rows"), list):
                raise ValueError("missing rows collection")
            items = parse_custom_stub_lake(payload, course, now=self.now)
        except Exception as exc:
            self.coverage.fail(course.id, "window", str(exc))
            self.course_errors[course.id] = str(exc)
            self.logger.exception("failed to parse %s", self.name)
            return
        if not items:
            self.logger.warning("%s parsed 0 tee times", self.name)
        self.coverage.complete(course.id, "window")
        yield from items

    def on_error(self, failure):
        course: CourseSpec = failure.request.meta["course"]
        self.coverage.fail(course.id, "window", failure.getErrorMessage())
        self.course_errors[course.id] = failure.getErrorMessage()
        self.logger.error("%s request failed: %s", self.name, self.course_errors[course.id])
