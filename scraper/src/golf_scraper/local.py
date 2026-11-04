"""Collect accessible courses into local JSON, once or on a 15-minute schedule.

No database, hosted services, login, browser automation or production writes.
Unavailable sources remain explicit; failures never refresh old observations.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

from parsel import Selector

from golfdb.catalog import CourseCatalog, CourseSpec, load_catalog, repo_root
from golf_scraper.pipelines import rejection_reason
from golf_scraper.spiders.miclub import parse_miclub_timesheet, sheet_date, timesheet_url

USER_AGENT = 'TeeTimeAggregator/0.1 (+local golf tee-time research scraper)'
INTERVAL_SECONDS = 15 * 60
MAX_RESPONSE_BYTES = 5 * 1024 * 1024


class SourceUnavailable(ValueError):
    pass


class SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl)[:2] != urlsplit(req.full_url)[:2]:
            raise SourceUnavailable('cross-origin redirect requires source review')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PublicHttp:
    """Serial, bounded public requests with per-origin delay and robots checks."""
    def __init__(self):
        self.opener = build_opener(SameOriginRedirect())
        self.policies: dict[str, RobotFileParser] = {}
        self.last_request: dict[str, float] = {}
        self.deadline = time.monotonic() + 540

    def _read(self, url: str, delay: float = 1) -> str:
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise SourceUnavailable('only public HTTPS URLs without credentials are supported')
        origin = f'{parsed.scheme}://{parsed.netloc}'
        wait = max(0, self.last_request.get(origin, 0) + delay - time.monotonic())
        if time.monotonic() + wait >= self.deadline:
            raise SourceUnavailable('nine-minute collection budget reached')
        time.sleep(wait)
        try:
            timeout = min(20, max(0.1, self.deadline - time.monotonic()))
            with self.opener.open(Request(url, headers={'User-Agent': USER_AGENT}), timeout=timeout) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise SourceUnavailable('source response exceeds size limit')
                return body.decode(response.headers.get_content_charset() or 'utf-8')
        finally:
            self.last_request[origin] = time.monotonic()

    def __call__(self, url: str) -> str:
        parsed = urlsplit(url)
        origin = f'{parsed.scheme}://{parsed.netloc}'
        if origin not in self.policies:
            policy = RobotFileParser()
            try:
                body = self._read(origin + '/robots.txt')
            except HTTPError as exc:
                if exc.code not in (404, 410):
                    raise SourceUnavailable(f'robots policy unavailable: HTTP {exc.code}') from exc
                body = 'User-agent: *\nDisallow:'
            if body.strip() and '<html' in body.lower():
                raise SourceUnavailable('robots policy returned an HTML page')
            policy.parse(body.splitlines())
            self.policies[origin] = policy
        policy = self.policies[origin]
        if not policy.can_fetch(USER_AGENT, url):
            raise SourceUnavailable('robots policy disallows this request')
        delay = max(1, policy.crawl_delay(USER_AGENT) or 0)
        rate = policy.request_rate(USER_AGENT)
        if rate and rate.requests:
            delay = max(delay, rate.seconds / rate.requests)
        return self._read(url, delay)


def validate_course(course: CourseSpec) -> list[dict]:
    if course.platform != 'miclub':
        raise SourceUnavailable(f'no verified local transport for {course.platform}')
    base = urlsplit(str(course.params.get('base_url', '')))
    booking = urlsplit(course.booking_url or '')
    if base.scheme != 'https' or not base.hostname or base.netloc != booking.netloc:
        raise SourceUnavailable('MiClub base URL must match the HTTPS booking host')
    if not str(course.params.get('booking_resource_id', '')).isdigit():
        raise SourceUnavailable('missing verified booking resource ID')
    groups = course.params.get('fee_groups')
    if not isinstance(groups, list) or not groups:
        raise SourceUnavailable('missing verified fee groups')
    ids = set()
    for group in groups:
        if (not isinstance(group, dict) or not str(group.get('id', '')).isdigit()
                or group.get('holes') not in course.holes_options or str(group['id']) in ids):
            raise SourceUnavailable('invalid or duplicate fee group configuration')
        ids.add(str(group['id']))
    return groups


def validate_calendar(html: str, course: CourseSpec, groups: list[dict]) -> None:
    if '</html>' not in html.lower():
        raise SourceUnavailable('incomplete calendar document')
    if re.search(r'publicCaptchaEnabled\s*=\s*true', html):
        raise SourceUnavailable('calendar requires CAPTCHA; approved source access needed')
    resource = re.search(r"var bookingResourceId\s*=\s*'([0-9]+)'", html)
    if not resource or resource[1] != str(course.params['booking_resource_id']):
        raise SourceUnavailable('calendar resource does not match course configuration')
    observed = set(Selector(text=html).css('.feeGroupRow::attr(data-feeid)').getall())
    if not {str(group['id']) for group in groups}.issubset(observed):
        raise SourceUnavailable('configured fee groups missing from public calendar')


def read_report(path: Path) -> dict:
    if not path.exists():
        return {'schema_version': 1, 'courses': {}}
    report = json.loads(path.read_text())
    if report.get('schema_version') != 1 or not isinstance(report.get('courses'), dict):
        raise ValueError('output is not a version 1 local collection report')
    return report


def save_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False, suffix='.tmp') as handle:
        temporary = Path(handle.name)
        json.dump(report, handle, indent=2)
        handle.write('\n')
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def output_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('another local collector owns this output; skipping') from exc
        yield


def error_label(exc: Exception) -> str:
    if isinstance(exc, HTTPError):
        return f'source returned HTTP {exc.code}'
    if isinstance(exc, URLError):
        return 'source network request failed'
    return str(exc)[:300]


def collect(catalog: CourseCatalog, previous: dict, *, now: datetime, days: int,
            first_date: date | None = None, fetch=None) -> dict:
    if now.tzinfo is None or not 1 <= days <= 15:
        raise ValueError('collection requires an aware clock and 1-15 days')
    fetch = fetch or PublicHttp()
    # JSON round-trip isolates this attempt from callers' previously saved results.
    report = json.loads(json.dumps(previous))
    report.update(schema_version=1, generated_at=now.isoformat(), interval_minutes=15)
    for course in catalog.courses:
        old = report['courses'].get(course.id, {})
        entry = {**old, 'name': course.name, 'timezone': course.timezone,
                 'booking_url': course.booking_url}
        report['courses'][course.id] = entry
        if course.params.get('collection_enabled') is not True:
            # A blocked source has unknown availability, never a verified empty list.
            entry.update(status=course.params.get('local_status', 'disabled'),
                         error=course.params.get('blocked_reason', 'collection disabled'))
            entry.pop('next_scheduled_at', None)
            continue
        interval = int(course.params.get('refresh_interval_minutes', 15))
        if interval < 15:
            raise ValueError('local sources must use a cadence of at least 15 minutes')
        last = old.get('last_attempt_at')
        next_due = datetime.fromisoformat(last) + timedelta(minutes=interval) if last else now
        if now < next_due:
            entry['next_scheduled_at'] = next_due.isoformat()
            continue
        first = first_date or now.astimezone(ZoneInfo(course.timezone)).date()
        today = now.astimezone(ZoneInfo(course.timezone)).date()
        if first < today or first + timedelta(days=days) > today + timedelta(days=15):
            raise ValueError('requested dates must be within today through day +14')
        entry.update(last_attempt_at=now.isoformat(), next_scheduled_at=(now + timedelta(minutes=interval)).isoformat())
        partitions = {key: value for key, value in old.get('partitions', {}).items()
                      if today.isoformat() <= key.split(':')[0] <= (today + timedelta(days=14)).isoformat()}
        entry['partitions'] = partitions
        attempted = []
        try:
            groups = validate_course(course)
            validate_calendar(fetch(course.booking_url), course, groups)
        except (ValueError, OSError, UnicodeError) as exc:
            entry.update(status='failed', error=error_label(exc))
            continue
        for offset in range(days):
            day = first + timedelta(days=offset)
            for group in groups:
                key = f"{day}:{group['id']}"
                attempted.append(key)
                partition = {**partitions.get(key, {}), 'last_attempt_at': now.isoformat()}
                partitions[key] = partition
                try:
                    url = timesheet_url(course, day, str(group['id']))
                    html = fetch(url)
                    if sheet_date(html) != day:
                        raise SourceUnavailable('tee sheet date does not match requested date')
                    params = {**course.params}
                    for field in ('public_fee_labels', 'excluded_fee_labels', 'fee_layout'):
                        if field in group:
                            params[field] = group[field]
                    scoped = course.model_copy(update={'params': params})
                    items = parse_miclub_timesheet(html, scoped, holes=group['holes'], booking_url=url, now=now)
                    rows = []
                    for item in items:
                        issue = rejection_reason(item, now=now)
                        if issue or item['spots_available'] > 4:
                            raise SourceUnavailable(issue or 'capacity exceeds one bookable group')
                        rows.append({**dict(item), 'starts_at': item['starts_at'].isoformat(),
                                     'source_partition': key, 'observed_at': now.isoformat()})
                    partition.update(status='complete' if rows else 'empty', error=None,
                                     last_success_at=now.isoformat(), tee_times=rows)
                except (ValueError, OSError, UnicodeError) as exc:
                    # Keep the previous observations and timestamps, marked as failed.
                    partition.update(status='failed', error=error_label(exc))
        good = sum(partitions[key]['status'] in ('complete', 'empty') for key in attempted)
        entry.update(status='complete' if good == len(attempted) else 'partial' if good else 'failed',
                     error=None if good == len(attempted) else f'{len(attempted) - good} requested partitions failed; see partition errors')
        entry['requested_partitions'] = attempted
        if good == len(attempted):
            entry['last_success_at'] = now.isoformat()
    return report


def summary(report: dict) -> None:
    for slug, course in report['courses'].items():
        rows = sum(len(p.get('tee_times', [])) for p in course.get('partitions', {}).values())
        print(f"{slug}: {course['status']} | {rows} saved offers", flush=True)
        if course.get('error'):
            print(f"  {course['error']}", flush=True)


def seconds_until_next_check(catalog: CourseCatalog, report: dict, now: datetime) -> float:
    due = [datetime.fromisoformat(report['courses'][c.id]['next_scheduled_at'])
           for c in catalog.courses if c.params.get('collection_enabled') is True]
    return max(0, (min(due) - now).total_seconds()) if due else INTERVAL_SECONDS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=repo_root() / 'scraper/courses.local.yaml')
    parser.add_argument('--output', type=Path, default=repo_root() / '.local/tee-times.json')
    parser.add_argument('--course', action='append', help='course slug; repeat to select multiple')
    parser.add_argument('--days', type=int, default=3, choices=range(1, 16), metavar='1..15')
    parser.add_argument('--date', type=date.fromisoformat, help='first local date; default is today')
    parser.add_argument('--watch', action='store_true', help='repeat every 15 minutes until Ctrl+C')
    parser.add_argument('--list', action='store_true', help='list course access status without network requests')
    args = parser.parse_args()
    try:
        catalog = load_catalog(args.catalog)
        if args.course:
            unknown = set(args.course) - {c.id for c in catalog.courses}
            if unknown:
                parser.error(f"unknown course(s): {', '.join(sorted(unknown))}")
            catalog = CourseCatalog(courses=[c for c in catalog.courses if c.id in args.course])
        if args.watch and args.date:
            parser.error('--date cannot be combined with --watch; watch follows the current local date')
        if args.list:
            for c in catalog.courses:
                print(f"{c.id}: {'enabled' if c.params.get('collection_enabled') is True else c.params.get('local_status', 'disabled')}")
            return
        with output_lock(args.output):
            while True:
                now = datetime.now(timezone.utc)
                report = collect(catalog, read_report(args.output), now=now, days=args.days, first_date=args.date)
                save_report(args.output, report)
                summary(report)
                if not args.watch:
                    selected = [report['courses'][c.id] for c in catalog.courses if c.params.get('collection_enabled') is True]
                    raise SystemExit(1 if any(c['status'] in ('partial', 'failed') for c in selected) else 0)
                # Follow saved due times, including after restarting watch mode
                # partway through an interval. Never overlap an active attempt.
                wait = seconds_until_next_check(catalog, report, datetime.now(timezone.utc))
                print(f'Next scheduled check in {wait / 60:.1f} minutes. Ctrl+C to stop.', flush=True)
                time.sleep(wait)
    except KeyboardInterrupt:
        print('Local collector stopped.', flush=True)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Local collection failed: {error_label(exc)}\n')


if __name__ == '__main__':
    main()
