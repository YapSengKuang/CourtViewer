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

from golf_scraper.coverage import Coverage
from golf_scraper.items import PRICE_UNIT_PER_ROUND, TeeTimeItem
from golf_scraper.window import WINDOW_DAYS, scrape_window
from golfdb.catalog import CourseSpec, load_catalog

PLATFORM = "miclub"
FIXTURE_NAME = "miclub_timesheet.html"
DATE_RE = re.compile(r"var selectedDate = '([^']+)'")


def sheet_date(html: str) -> date:
    match = DATE_RE.search(html)
    if not match:
        raise ValueError("miclub timesheet is missing selectedDate")
    value = match[1]
    try:
        return datetime.strptime(value, "%d-%m-%Y").date()
    except ValueError:
        parts = value.split()
        if len(parts) != 6:
            raise ValueError("unrecognised selectedDate")
        return datetime.strptime(f"{parts[1]} {parts[2]} {parts[5]}", "%b %d %Y").date()


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
    """Read complete sheets, preserving each provider row as a bookable group."""
    day = sheet_date(html)
    if "</html>" not in html.lower():
        raise ValueError("incomplete timesheet document")
    window_start, window_end = scrape_window(course.timezone, now)
    zone = ZoneInfo(course.timezone)
    selector = Selector(text=html)
    rows = selector.css(".teetime-day-table div.row-time")
    if not rows:
        # Empty sheets need a positively identified empty-state marker. An
        # unrecognised/login/changed layout must never erase stored availability.
        empty = selector.css(".teetime-day-table .no-tee-times")
        if not empty or "no tee times available" not in empty.xpath("string(.)").get("").lower():
            raise ValueError("timesheet has no recognised rows or verified empty marker")
    groups = {}
    for row in rows:
        starts_at = _starts_at(row, day, zone)
        row_id = row.attrib.get("data-value")
        if starts_at is None or not row_id or not row_id.isdigit():
            raise ValueError("timesheet row missing time or provider row id")
        cells = row.css(".records-wrapper .cell")
        if not cells:
            raise ValueError("timesheet row missing booking cells")
        if any(not ({'cell-available', 'cell-taken'} & set(cell.attrib.get('class', '').split())) for cell in cells):
            raise ValueError("timesheet contains unrecognised booking-cell states")
        spots = len(row.css("div.cell-available"))
        if spots == 0:
            continue  # A recognised sold-out row verifies coverage, not availability.
        price = _public_price(row, course)
        if price is None:
            raise ValueError("available row missing public adult price")
        if not (window_start <= starts_at < window_end) or starts_at < now:
            continue
        item = TeeTimeItem(course_slug=course.id, starts_at=starts_at, holes=holes,
            spots_available=spots, price_per_player=price, currency="AUD",
            price_unit=PRICE_UNIT_PER_ROUND, booking_url=booking_url, source_slot_key=row_id)
        if row_id in groups and groups[row_id] != item:
            raise ValueError("conflicting duplicate provider row")
        groups[row_id] = item
    return sorted(groups.values(), key=lambda item: (item['starts_at'], item['source_slot_key']))


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
        self.coverage = Coverage()
        # Register all expected sheets before requests are yielded.
        for course in self.courses:
            zone = ZoneInfo(course.timezone)
            first = self.now.astimezone(zone).date()
            for offset in range(WINDOW_DAYS):
                day = first + timedelta(days=offset)
                for group in course.params.get("fee_groups", []):
                    if int(group["holes"]) in course.holes_options:
                        start = datetime(day.year, day.month, day.day, tzinfo=zone)
                        self.coverage.expect(course.id, f"{day}:{group['id']}", start, start + timedelta(days=1))

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
                        meta={"course": course, "holes": holes, "fee_group_id": fee_group_id,
                              "partition_key": f"{day}:{fee_group_id}", "expected_date": day},
                    )

    def parse(self, response):
        course: CourseSpec = response.meta["course"]
        holes = int(response.meta["holes"])
        booking_url = response.url
        key = response.meta["partition_key"]
        try:
            if sheet_date(response.text) != response.meta["expected_date"]:
                raise ValueError("response date does not match requested partition")
            items = parse_miclub_timesheet(
                response.text,
                course,
                holes=holes,
                booking_url=booking_url,
                now=self.now,
            )
        except Exception as exc:
            self.coverage.fail(course.id, key, str(exc))
            self.course_errors[course.id] = str(exc)
            self.logger.exception("failed to parse %s for %s", self.name, course.id)
            return
        self.coverage.complete(course.id, key)
        for item in items:
            item["source_partition"] = key
            yield item

    def on_error(self, failure):
        course: CourseSpec = failure.request.meta["course"]
        self.coverage.fail(course.id, failure.request.meta["partition_key"], failure.getErrorMessage())
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


def _public_price(row: Selector, course: CourseSpec) -> str | None:
    for item in row.css(".fees-wrapper li"):
        label = " ".join(part.strip() for part in item.css("::text").getall())
        lowered = label.lower()
        configured = course.params.get("public_fee_labels", [])
        fee_label = " ".join(PRICE_RE.sub("", lowered).split())
        if "junior" in lowered or "concession" in lowered:
            continue
        if configured:
            if fee_label not in [label.lower() for label in configured]:
                continue
        elif "public" not in lowered:
            continue
        price = PRICE_RE.search(label)
        if price is not None:
            return price.group(1)
    return None
