"""Read-only local preview API for the Python collector's JSON report."""
from datetime import date, datetime, time, timedelta
import json
import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import AwareDatetime, BaseModel, Field, ValidationError

from golfdb.catalog import load_catalog, repo_root
from tee_api.deps import get_now
from tee_api.schemas import TeeTimeList, TeeTimeOut

app = FastAPI(title='Local collected tee times', version='0.1.0')
app.add_middleware(CORSMiddleware,
    allow_origins=['http://localhost:3000', 'http://localhost:3001',
                   'http://127.0.0.1:3000', 'http://127.0.0.1:3001'],
    allow_methods=['GET'], allow_headers=['*'])
OBSERVATION_WINDOW = timedelta(hours=24)


class StoredOffer(BaseModel):
    course_slug: str
    source_partition: str
    source_slot_key: str = Field(min_length=1, max_length=200)
    starts_at: AwareDatetime
    observed_at: AwareDatetime
    holes: Literal[9, 18]
    spots_available: int = Field(ge=1, le=4)
    price_per_player: str
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    booking_url: str


class StoredPartition(BaseModel):
    status: Literal['complete', 'empty']
    last_success_at: AwareDatetime
    tee_times: list[StoredOffer]


class CoverageOut(BaseModel):
    slug: str
    name: str
    status: Literal['complete', 'incomplete', 'unchecked', 'outside_horizon']
    availability_status: Literal['available', 'empty', 'unavailable', 'stale', 'unchecked', 'outside_horizon']
    observed_at: datetime | None = None
    refresh_interval_minutes: int = 15
    expected: int
    checked: int


class LocalSearchResult(TeeTimeList):
    coverage: list[CoverageOut]


def local_snapshot(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    path = Path(os.environ.get('GOLF_LOCAL_REPORT', repo_root() / '.local/tee-times.json'))
    try:
        if path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError('oversized report')
        report = json.loads(path.read_text())
        if (not isinstance(report, dict) or report.get('schema_version') != 1
                or not isinstance(report.get('courses'), dict)):
            raise ValueError('invalid report')
        catalog = load_catalog(repo_root() / 'scraper/courses.local.yaml')
    except (OSError, ValueError) as exc:
        raise HTTPException(503, 'Local collection data unavailable. Run the local collector first.') from exc
    courses = [c for c in catalog.courses if c.params.get('collection_enabled') is True]
    return courses, report['courses']


@app.get('/api/courses')
def list_courses(snapshot=Depends(local_snapshot), now: datetime = Depends(get_now)):
    courses, saved = snapshot
    result = []
    for course in courses:
        today = now.astimezone(ZoneInfo(course.timezone)).date()
        entry = saved.get(course.id, {})
        days = []
        for key in entry.get('partitions', {}):
            try:
                day = date.fromisoformat(key.split(':')[0])
                if today <= day <= today + timedelta(days=14):
                    days.append(day)
            except ValueError:
                continue
        result.append({
            'slug': course.id, 'name': course.name, 'timezone': course.timezone,
            'date_from': min(days, default=today), 'date_to': max(days, default=today),
            'refresh_interval_minutes': 15, 'next_scheduled_at': entry.get('next_scheduled_at'),
        })
    return {'courses': sorted(result, key=lambda c: c['name']), 'source': 'local'}


def project_partition(raw, course, group, key, day, now):
    """Validate the entire saved scope before exposing any of its offers."""
    partition = StoredPartition.model_validate(raw)
    observed = partition.last_success_at
    if not now - OBSERVATION_WINDOW <= observed <= now:
        return [], 'stale', observed
    if (partition.status == 'empty') != (not partition.tee_times):
        raise ValueError('inconsistent empty state')
    zone = ZoneInfo(course.timezone)
    rows = []
    identities = set()
    for item in partition.tee_times:
        link = urlsplit(item.booking_url)
        if (item.course_slug != course.id or item.source_partition != key
                or item.holes != group['holes'] or item.starts_at.astimezone(zone).date() != day
                or item.observed_at != observed or item.starts_at <= observed
                or link.scheme != 'https' or link.netloc != urlsplit(course.booking_url).netloc
                or link.username or link.password or item.source_slot_key in identities):
            raise ValueError('offer does not match expected source scope')
        identities.add(item.source_slot_key)
        row = TeeTimeOut(
            source_partition=key, source_slot_key=item.source_slot_key,
            course_slug=course.id, course_name=course.name,
            address=course.address, lat=course.lat, lng=course.lng, timezone=course.timezone,
            holes=item.holes, price_per_player=item.price_per_player, currency=item.currency,
            starts_at=item.starts_at, starts_at_local=item.starts_at.astimezone(zone),
            spots_available=item.spots_available, booking_url=item.booking_url, scraped_at=observed)
        if not row.price_per_player.is_finite() or row.price_per_player < 0:
            raise ValueError('invalid price')
        if item.starts_at > now:
            rows.append(row)
    return rows, 'checked', observed


@app.get('/api/tee-times', response_model=LocalSearchResult)
def search_tee_times(
    date: date, time_from: time, time_to: time,
    players: int = Query(..., ge=1, le=4), holes: int | None = None,
    course_slug: str | None = None, sort: Literal['starts_at', 'price'] = 'starts_at',
    limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0, le=10000),
    snapshot=Depends(local_snapshot), now: datetime = Depends(get_now),
) -> LocalSearchResult:
    if holes is not None and holes not in (9, 18):
        raise HTTPException(422, 'holes must be 9 or 18')
    if time_from.tzinfo or time_to.tzinfo or time_from > time_to:
        raise HTTPException(422, 'Provide a valid local time window without a timezone offset')
    courses, saved = snapshot
    if course_slug:
        courses = [c for c in courses if c.id == course_slug]
        if not courses:
            raise HTTPException(422, 'Unknown or disabled local course')
    results, coverage = [], []
    for course in courses:
        if holes is not None and holes not in course.holes_options:
            continue
        today = now.astimezone(ZoneInfo(course.timezone)).date()
        groups = [g for g in course.params['fee_groups'] if holes is None or g['holes'] == holes]
        item = CoverageOut(slug=course.id, name=course.name, expected=len(groups), checked=0,
                           status='unchecked', availability_status='unchecked')
        if not today <= date <= today + timedelta(days=14):
            item.status = item.availability_status = 'outside_horizon'
            coverage.append(item)
            continue
        entry = saved.get(course.id, {})
        partitions = entry.get('partitions', {})
        source_failed = entry.get('status') == 'failed'
        states, observed_times, rows = [], [], []
        for group in groups:
            key = f"{date}:{group['id']}"
            raw = partitions.get(key)
            if raw is None:
                states.append('unchecked')
                continue
            if source_failed or not isinstance(raw, dict) or raw.get('status') not in ('complete', 'empty'):
                states.append('unavailable')
                continue
            try:
                offers, state, observed = project_partition(raw, course, group, key, date, now)
            except (ValidationError, ValueError, TypeError):
                states.append('unavailable')
                continue
            states.append(state)
            if state == 'checked':
                item.checked += 1
                observed_times.append(observed)
                rows.extend(offers)
        if groups and item.checked == len(groups):
            item.status = 'complete'
            item.availability_status = 'available' if rows else 'empty'
        elif states and any(s != 'unchecked' for s in states):
            item.status = 'incomplete'
            item.availability_status = 'stale' if all(s == 'stale' for s in states) else 'unavailable'
        item.observed_at = min(observed_times, default=None)
        coverage.append(item)
        results.extend(row for row in rows if row.spots_available >= players
                       and (holes is None or row.holes == holes)
                       and time_from <= row.starts_at_local.time().replace(tzinfo=None) <= time_to)
    tie = lambda row: (row.starts_at, row.course_name, row.holes, row.source_partition, row.source_slot_key)
    results.sort(key=(lambda row: (row.currency, row.price_per_player, *tie(row))) if sort == 'price' else tie)
    page = results[offset:offset + limit + 1]
    return LocalSearchResult(tee_times=page[:limit], has_more=len(page) > limit, coverage=coverage)


@app.get('/api/health')
def health(snapshot=Depends(local_snapshot)):
    courses, saved = snapshot
    return {'source': 'local', 'courses': [
        {'slug': c.id, 'name': c.name, 'last_success_at': saved.get(c.id, {}).get('last_success_at'),
         'last_item_count': sum(len(p.get('tee_times', [])) for p in saved.get(c.id, {}).get('partitions', {}).values()),
         'last_error': None if saved.get(c.id, {}).get('status') == 'complete' else 'Local collection incomplete'}
        for c in courses]}
