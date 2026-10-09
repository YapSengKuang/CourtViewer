"""MiClub public tee sheets.

The timesheet is server-rendered HTML. There is no JSON feed on the public
booking page. One spider covers every course whose platform is miclub.
"""

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import scrapy
from parsel import Selector

from golf_scraper.items import PRICE_UNIT_PER_ROUND, TeeTimeItem
from golf_scraper.window import WINDOW_DAYS, scrape_window
from golfdb.catalog import CourseSpec, load_catalog

PLATFORM = "miclub"
FIXTURE_NAME = "miclub_timesheet.html"
DATE_RE = re.compile(r"var selectedDate = '(\d{2})-(\d{2})-(\d{4})'")
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*(am|pm)", re.I)
PRICE_RE = re.compile(r"\$(\d+(?:\.\d+)?)")


def fixture_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "tests" / "fixtures" / FIXTURE_NAME
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(FIXTURE_NAME)


def parse_miclub_timesheet(
    html: str,
    course: CourseSpec,
    *,
    holes: int,
    booking_url: str,
    now: datetime,
) -> list[TeeTimeItem]:
    """Turn one MiClub public timesheet into TeeTimeItems.

    1st tee and 10th tee rows that share a start time are combined. Spots are
    the sum of open cells. The price is the public adult fee, not junior.
    """
    match = DATE_RE.search(html)
    if match is None:
        raise ValueError("miclub timesheet is missing selectedDate")
    day = date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    window_start, window_end = scrape_window(course.timezone, now)
    zone = ZoneInfo(course.timezone)
    combined: dict[datetime, TeeTimeItem] = {}

    for row in Selector(text=html).css("div.row-time"):
        starts_at = _starts_at(row, day, zone)
        if starts_at is None or not (window_start <= starts_at < window_end):
            continue
        price = _public_price(row)
        if price is None:
            continue
        spots = len(row.css("div.cell-available"))
        existing = combined.get(starts_at)
        if existing is None:
            combined[starts_at] = TeeTimeItem(
                course_slug=course.id,
                starts_at=starts_at,
                holes=holes,
                spots_available=spots,
                price_per_player=price,
                currency="AUD",
                price_unit=PRICE_UNIT_PER_ROUND,
                booking_url=booking_url,
            )
            continue
        existing["spots_available"] = int(existing["spots_available"]) + spots

    return [combined[key] for key in sorted(combined)]


def timesheet_url(course: CourseSpec, day: date, fee_group_id: str) -> str:
    base = str(course.params["base_url"]).rstrip("/")
    query = urlencode(
        {
            "bookingResourceId": course.params["booking_resource_id"],
            "selectedDate": day.isoformat(),
            "feeGroupId": fee_group_id,
        }
    )
    return f"{base}/guests/bookings/ViewPublicTimesheet.msp?{query}"


class MiClubSpider(scrapy.Spider):
    name = PLATFORM
    platform = PLATFORM

    def __init__(self, *args, **kwargs):
        now = kwargs.pop("now", None)
        super().__init__(*args, **kwargs)
        self.now = now if isinstance(now, datetime) else datetime.now(timezone.utc)
        self.run_started_at = self.now
        self.courses = [course for course in load_catalog().courses if course.platform == self.platform]
        self.course_slugs = [course.id for course in self.courses]
        self.course_errors: dict[str, str] = {}

    async def start(self):
        for request in self.iter_requests():
            yield request

    def iter_requests(self):
        if not self.courses:
            self.logger.warning("no courses in courses.yaml use platform %s", self.platform)
        for course in self.courses:
            zone = ZoneInfo(course.timezone)
            first_day = self.now.astimezone(zone).date()
            fee_groups = course.params.get("fee_groups") or []
            if not fee_groups:
                self.course_errors[course.id] = "miclub course is missing fee_groups"
                self.logger.error("%s", self.course_errors[course.id])
                continue
            for offset in range(WINDOW_DAYS):
                day = first_day + timedelta(days=offset)
                for group in fee_groups:
                    holes = int(group["holes"])
                    if holes not in course.holes_options:
                        continue
                    fee_group_id = str(group["id"])
                    yield scrapy.Request(
                        url=timesheet_url(course, day, fee_group_id),
                        callback=self.parse,
                        errback=self.on_error,
                        meta={"course": course, "holes": holes, "fee_group_id": fee_group_id},
                    )

    def parse(self, response):
        course: CourseSpec = response.meta["course"]
        holes = int(response.meta["holes"])
        booking_url = response.url
        try:
            items = parse_miclub_timesheet(
                response.text,
                course,
                holes=holes,
                booking_url=booking_url,
                now=self.now,
            )
        except Exception as exc:
            self.course_errors[course.id] = str(exc)
            self.logger.exception("failed to parse %s for %s", self.name, course.id)
            return
        yield from items

    def on_error(self, failure):
        course: CourseSpec = failure.request.meta["course"]
        self.course_errors[course.id] = failure.getErrorMessage()
        self.logger.error("%s request failed for %s: %s", self.name, course.id, self.course_errors[course.id])


def _starts_at(row: Selector, day: date, zone: ZoneInfo) -> datetime | None:
    text = " ".join(row.css(".time-wrapper h3::text").getall())
    match = TIME_RE.search(text)
    if match is None:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    meridiem = match.group(3).lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone)
    return local.astimezone(timezone.utc)


def _public_price(row: Selector) -> str | None:
    for item in row.css(".fees-wrapper li"):
        label = " ".join(part.strip() for part in item.css("::text").getall())
        lowered = label.lower()
        if "public" not in lowered or "junior" in lowered:
            continue
        price = PRICE_RE.search(label)
        if price is not None:
            return price.group(1)
    return None
