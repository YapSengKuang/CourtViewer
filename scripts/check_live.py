"""Read-only hosted API smoke test; never contacts golf providers or writes data."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
from time import perf_counter
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from golfdb.catalog import load_catalog, repo_root


def public_settings():
    settings = dict(os.environ)
    path = repo_root() / 'web/.env.local'
    if path.exists():
        for line in path.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                if key.startswith('NEXT_PUBLIC_'):
                    settings.setdefault(key.strip(), value.strip().strip('\"\''))
    return settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    settings = public_settings()
    base = settings['NEXT_PUBLIC_SUPABASE_URL'].rstrip('/')
    key = settings['NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY']
    if urlsplit(base).scheme != 'https' or not key.startswith('sb_publishable_'):
        raise ValueError('Hosted HTTPS URL and public publishable key are required')
    started = perf_counter()
    def call(path, payload=None):
        request = Request(base + '/rest/v1/' + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'apikey': key, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=15) as response:
            return json.load(response)
    courses = call('rpc/golf_courses', {})['courses']
    catalog = load_catalog(repo_root() / 'scraper/courses.live.yaml')
    expected = {c.id for c in catalog.courses}
    actual = {c['slug']: c for c in courses}
    if not expected <= actual.keys():
        raise ValueError('Verified launch courses are not all publicly enabled')
    for course in catalog.courses:
        assert actual[course.id]['holes_options'] == course.holes_options
    now = datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo('Australia/Melbourne')).date()
    hosts = {c.id: urlsplit(c.booking_url).hostname for c in catalog.courses}
    hosts['freeway'] = 'freeway.quick18.com'
    summaries = []
    for offset in (0, 1, 14):
        day = today + timedelta(days=offset)
        payload = {'p_date': str(day), 'p_time_from': '00:00', 'p_time_to': '23:59',
            'p_players': 2, 'p_holes': None, 'p_limit': 200, 'p_offset': 0}
        total = 0
        identities = set()
        while True:
            result = call('rpc/golf_search_v3', payload)
            assert len(result['tee_times']) <= 200
            assert expected <= {c['slug'] for c in result['coverage']}
            for coverage in result['coverage']:
                if coverage['slug'] in expected:
                    assert coverage['status'] == 'complete', f"{coverage['slug']} {day}: coverage incomplete"
                    observed = datetime.fromisoformat(coverage['observed_at'])
                    assert now - timedelta(minutes=45) <= observed <= datetime.now(timezone.utc), f"{coverage['slug']}: collection is late"
            for row in result['tee_times']:
                absolute = datetime.fromisoformat(row['starts_at'])
                observed = datetime.fromisoformat(row['scraped_at'])
                assert absolute > now and now - timedelta(hours=24) <= observed <= datetime.now(timezone.utc)
                assert absolute.astimezone(ZoneInfo(row['timezone'])).date() == day
                assert 2 <= row['spots_available'] <= 4 and row['holes'] in (9, 18)
                assert Decimal(row['price_per_player']).is_finite() and Decimal(row['price_per_player']) >= 0
                link = urlsplit(row['booking_url'])
                assert link.scheme == 'https' and link.hostname == hosts[row['course_slug']]
                identity = (row['course_slug'], row['source_partition'], row['source_slot_key'], row['holes'])
                assert identity not in identities
                identities.add(identity)
            total += len(result['tee_times'])
            if not result['has_more']:
                break
            payload['p_offset'] += 200
            assert payload['p_offset'] <= 10000
        summaries.append({'date': str(day), 'offers': total, 'coverage': result['coverage']})
    eighteen = call('rpc/golf_search_v3', {**payload, 'p_offset': 0, 'p_holes': 18})
    assert 'morack' not in {c['slug'] for c in eighteen['coverage']}
    try:
        call('tee_times?select=id&limit=1')
    except HTTPError as exc:
        assert exc.code in (401, 403)
    else:
        raise AssertionError('Direct anonymous table access unexpectedly allowed')
    try:
        call('rpc/golf_search_v3', {**payload, 'p_players': 5})
    except HTTPError as exc:
        assert exc.code == 400
    else:
        raise AssertionError('Invalid party size unexpectedly accepted')
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'status': 'passed',
        'elapsed_seconds': round(perf_counter() - started, 2), 'course_count': len(courses), 'dates': summaries,
        'anonymous_table_access': 'denied', 'invalid_input': 'rejected', 'morack_18_holes': 'unsupported'}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
