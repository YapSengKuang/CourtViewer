"""Import saved Freeway HTML into isolated, sanitised demo data (never Postgres)."""

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit
from zoneinfo import ZoneInfo

from golfdb.catalog import load_catalog, repo_root
from golf_scraper.spiders.quick18 import date_url, parse_matrix


def import_snapshot(html: str, *, source_url: str, day: date, captured_at: datetime) -> dict:
    if captured_at.tzinfo is None or captured_at > datetime.now(timezone.utc):
        raise ValueError('capture timestamp must have a timezone and cannot be in the future')
    source = urlsplit(source_url)
    if (source.scheme != 'https' or source.netloc != 'freeway.quick18.com'
            or source.path != '/teetimes/searchmatrix'):
        raise ValueError('source must be the Freeway HTTPS matrix')
    query = parse_qs(source.query)
    if 'teedate' in query and query['teedate'] != [day.strftime('%Y%m%d')]:
        raise ValueError('source URL date does not match requested date')
    course = load_catalog(repo_root() / 'scraper/courses.freeway.yaml').courses[0]
    if captured_at.astimezone(ZoneInfo(course.timezone)).date() > day:
        raise ValueError('capture must not be after the requested local date')
    items = parse_matrix(html, course, day=day, now=captured_at)
    if not items:
        raise ValueError('no future standard offers at capture time; empty layouts remain unverified')
    offers = []
    for item in items:
        identity = item['source_slot_key']
        provider_id, _, rate_id = identity.split(':')
        link = urlsplit(item['booking_url'])
        offers.append({
            'id': identity, 'starts_at': item['starts_at'].isoformat(),
            'local_time': item['starts_at'].astimezone(ZoneInfo(course.timezone)).strftime('%H:%M'),
            'starting_course': course.params['provider_courses'][provider_id],
            'holes': item['holes'], 'spots_available': item['spots_available'],
            'price_per_player': item['price_per_player'], 'currency': 'AUD',
            'booking_url': f'https://freeway.quick18.com{link.path}?{urlencode({"psid": rate_id, "p": "0"})}',
        })
    return {
        'schema_version': 1, 'kind': 'snapshot', 'course_slug': 'freeway',
        'date': day.isoformat(), 'timezone': course.timezone,
        'captured_at': captured_at.astimezone(timezone.utc).isoformat(),
        'source_url': date_url(course, day),
        'source_sha256': hashlib.sha256(html.encode()).hexdigest(), 'offers': offers,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path)
    parser.add_argument('--source-url', required=True)
    parser.add_argument('--date', required=True, type=date.fromisoformat)
    parser.add_argument('--captured-at', required=True, type=datetime.fromisoformat)
    parser.add_argument('--output', required=True, type=Path,
                        help='isolated JSON bundle; replaces only this date, preserves other dates')
    args = parser.parse_args()
    try:
        snapshot = import_snapshot(args.html.read_text(), source_url=args.source_url,
                                   day=args.date, captured_at=args.captured_at)
        bundle = json.loads(args.output.read_text()) if args.output.exists() else []
        if not isinstance(bundle, list) or any(s.get('kind') != 'snapshot' for s in bundle):
            raise ValueError('output is not a snapshot bundle')
        previous = next((s for s in bundle if s['date'] == snapshot['date']), None)
        if previous and datetime.fromisoformat(previous['captured_at']) > args.captured_at:
            raise ValueError('refusing to replace a newer capture')
        bundle = [s for s in bundle if s['date'] != snapshot['date']] + [snapshot]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix('.tmp')
        temporary.write_text(json.dumps(sorted(bundle, key=lambda s: s['date']), indent=2) + '\n')
        temporary.replace(args.output)
    except (ValueError, KeyError, TypeError, IndexError, OSError) as exc:
        parser.exit(1, f'Snapshot rejected: {exc}\n')
    print(f"Imported {len(snapshot['offers'])} offers for {snapshot['date']} (snapshot only)")


if __name__ == '__main__':
    main()
