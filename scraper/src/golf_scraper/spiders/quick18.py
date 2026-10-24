"""Candidate Quick18 matrix adapter. Freeway collection is disabled by default.

Only an unfiltered, date-matched matrix can verify coverage. Empty/release-window
layouts have not been captured, so they deliberately fail closed. An approved
feed may require replacing the transport; this module does not bypass robots.
"""

import re
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from zoneinfo import ZoneInfo
from sqlalchemy import select
from golfdb.models import ScrapeExecution
from golfdb.session import get_engine

import scrapy
from parsel import Selector

from golfdb.catalog import CourseSpec, load_catalog
from golf_scraper.coverage import Coverage
from golf_scraper.items import PRICE_UNIT_PER_ROUND, TeeTimeItem
from golf_scraper.window import WINDOW_DAYS


def date_url(course: CourseSpec, day: date) -> str:
    base = urlsplit(course.booking_url or '')
    if base.scheme != 'https' or not base.hostname or base.path != '/teetimes/searchmatrix':
        raise ValueError('Quick18 requires an HTTPS matrix URL')
    return f'https://{base.netloc}{base.path}?{urlencode({"teedate": day.strftime("%Y%m%d")})}'


def _text(node: Selector) -> str:
    return ' '.join(node.xpath('string(.)').get('').split())


def parse_matrix(html: str, course: CourseSpec, *, day: date, now: datetime) -> list[TeeTimeItem]:
    if now.tzinfo is None:
        raise ValueError('now must be timezone-aware')
    if '</html>' not in html.lower():
        raise ValueError('incomplete matrix document')
    page = Selector(text=html)
    selected = page.css('#SearchForm_Date::attr(value)').get()
    if not selected or datetime.strptime(selected, '%d/%m/%Y').date() != day:
        raise ValueError('response date does not match requested date')
    for field, expected in (('CourseId', '0'), ('Players', '0'), ('TimeOfDay', 'Any')):
        if page.css(f'#SearchForm_{field} option[selected]::attr(value)').get() != expected:
            raise ValueError('matrix must be unfiltered')
    tables = page.css('table.matrixTable')
    if len(tables) != 1:
        raise ValueError('missing or ambiguous matrix')
    headers = [_text(node) for node in tables.css('thead .matrixHdrSched')]
    rates = course.params.get('standard_rates', {})
    provider_courses = course.params.get('provider_courses', {})
    if not rates or not provider_courses or not set(rates).issubset(headers) or len(headers) != len(set(headers)):
        raise ValueError('unrecognised matrix rates or missing course configuration')
    rows = tables.css('tbody > tr')
    if not rows:
        raise ValueError('empty or unreleased matrix is not yet verified')
    groups = {}
    zone = ZoneInfo(course.timezone)
    for row in rows:
        cells = row.css('td.matrixsched')
        if len(cells) != len(headers):
            raise ValueError('incomplete matrix row')
        capacity_label = _text(row.css('.matrixPlayers')[0]) if row.css('.matrixPlayers') else ''
        capacities = {'1 player': 1, '1 or 2 players': 2, '1 to 3 players': 3, '1 to 4 players': 4}
        if capacity_label not in capacities:
            raise ValueError('unsupported group capacity')
        label = _text(row.css('.mtrxCourse')[0]) if row.css('.mtrxCourse') else ''
        clock = _text(row.css('.mtrxTeeTimes')[0]) if row.css('.mtrxTeeTimes') else ''
        local = datetime.strptime(f'{day.isoformat()} {clock.replace(" ", "")}', '%Y-%m-%d %I:%M%p').replace(tzinfo=zone)
        for header, cell in zip(headers, cells):
            if header not in rates:
                continue  # Concession, junior and twilight offers are not standard rounds.
            rate = rates[header]
            holes = rate['holes']
            if holes not in (9, 18) or holes not in course.holes_options:
                raise ValueError('unsupported rate holes')
            links = cell.css('.mtrxSelect a::attr(href)').getall()
            if 'mtrxInactive' in cell.attrib.get('class', '').split():
                notices = cell.css('.mtrxAvailMessage')
                if links or len(notices) != 1 or _text(notices[0]) != 'Rate not available for date selected':
                    raise ValueError('unrecognised unavailable rate')
                continue
            prices = cell.css('.mtrxPrice')
            if len(links) != 1 or len(prices) != 1 or not re.fullmatch(r'\$\d+\.\d{2}', _text(prices[0])):
                raise ValueError('missing standard price or booking link')
            link = urljoin(course.booking_url, links[0])
            parsed = urlsplit(link)
            match = re.fullmatch(r'/teetimes/course/(\d+)/teetime/(\d{12})', parsed.path)
            query = parse_qs(parsed.query)
            if (parsed.scheme != 'https' or parsed.netloc != urlsplit(course.booking_url).netloc
                    or not match or query.get('psid') != [str(rate['id'])]
                    or query.get('p') != ['0']):
                raise ValueError('unexpected booking link or rate identity')
            provider_id, timestamp = match.groups()
            if provider_courses.get(provider_id) != label or timestamp != local.strftime('%Y%m%d%H%M'):
                raise ValueError('booking group or time does not match row')
            starts = local.astimezone(timezone.utc)
            if starts <= now:
                continue
            # Rate is part of identity; separate starting tees are never combined.
            identity = f'{provider_id}:{timestamp}:{rate["id"]}'
            item = TeeTimeItem(course_slug=course.id, starts_at=starts, holes=holes,
                spots_available=capacities[capacity_label],
                price_per_player=str(Decimal(_text(prices[0])[1:])), currency='AUD',
                price_unit=PRICE_UNIT_PER_ROUND, booking_url=link,
                source_partition=day.isoformat(), source_slot_key=identity)
            if identity in groups and groups[identity] != item:
                raise ValueError('conflicting duplicate bookable group')
            groups[identity] = item
    return sorted(groups.values(), key=lambda item: (item['starts_at'], item['source_slot_key']))


class Quick18Spider(scrapy.Spider):
    name = 'quick18'
    # Evaluate the policy for Scrapy explicitly; do not evade its named exclusion
    # by relying on the application's custom descriptive User-Agent.
    custom_settings = {'ROBOTSTXT_OBEY': True, 'ROBOTSTXT_USER_AGENT': 'Scrapy'}

    def __init__(self, *args, **kwargs):
        now = kwargs.pop('now', None)
        super().__init__(*args, **kwargs)
        self.now = now if isinstance(now, datetime) else datetime.now(timezone.utc)
        self.run_started_at = self.now
        self.courses = [c for c in load_catalog().courses if c.platform == self.name]
        if any(c.params.get('collection_enabled') is not True or not c.params.get('access_reference') for c in self.courses):
            raise ValueError('Quick18 collection is disabled pending an approved access method and live acceptance')
        self.agreed_daily = any(c.params.get('access_mode') == 'agreed_public_matrix_daily' for c in self.courses)
        if self.agreed_daily:
            if len(self.courses) != 1 or self.courses[0].id != 'freeway' or urlsplit(self.courses[0].booking_url).netloc != 'freeway.quick18.com':
                raise ValueError('daily access agreement is scoped to Freeway only')
            engine = get_engine()
            try:
                with engine.connect() as connection:
                    marker = connection.execute(select(ScrapeExecution).where(
                        ScrapeExecution.id == os.environ.get('FREEWAY_DAILY_ATTEMPT_ID'),
                        ScrapeExecution.spider == 'quick18_daily_attempt',
                        ScrapeExecution.status == 'running')).first()
                    if not marker or not timedelta(0) <= self.now - marker.started_at < timedelta(minutes=10):
                        raise ValueError('agreed Freeway access requires the guarded daily runner')
            finally:
                engine.dispose()
        self.course_slugs = [c.id for c in self.courses]
        self.course_errors = {}
        self.coverage = Coverage()
        for course in self.courses:
            zone = ZoneInfo(course.timezone)
            today = self.now.astimezone(zone).date()
            for offset in range(WINDOW_DAYS):
                day = today + timedelta(days=offset)
                start = datetime.combine(day, datetime.min.time(), zone)
                self.coverage.expect(course.id, day.isoformat(), start, start + timedelta(days=1))

    async def start(self):
        for request in self.iter_requests():
            yield request

    def iter_requests(self):
        for course in self.courses:
            for slug, key in self.coverage.partitions:
                if slug == course.id:
                    yield scrapy.Request(date_url(course, date.fromisoformat(key)), callback=self.parse,
                        errback=self.on_error, meta={'course': course, 'partition_key': key,
                            'dont_obey_robotstxt': self.agreed_daily, 'dont_retry': self.agreed_daily})

    def parse(self, response):
        course, key = response.meta['course'], response.meta['partition_key']
        try:
            items = parse_matrix(response.text, course, day=date.fromisoformat(key), now=self.now)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            self.coverage.fail(course.id, key, str(exc))
            self.course_errors[course.id] = str(exc)
            return
        self.coverage.complete(course.id, key)
        yield from items

    def on_error(self, failure):
        course, key = failure.request.meta['course'], failure.request.meta['partition_key']
        self.coverage.fail(course.id, key, failure.getErrorMessage())
        self.course_errors[course.id] = failure.getErrorMessage()
