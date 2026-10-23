import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from golf_scraper.snapshots import import_snapshot

HTML = (Path(__file__).parent / 'fixtures/freeway_matrix.html').read_text()
ARGS = dict(source_url='https://freeway.quick18.com/teetimes/searchmatrix?teedate=20261024',
            day=date(2026, 10, 24), captured_at=datetime(2026, 10, 23, 13, tzinfo=timezone.utc))


def test_snapshot_has_capture_provenance_and_no_personal_or_tracking_content():
    html = HTML.replace('</body>', '<script>personal@example.com</script></body>')
    html = html.replace('psid=10537&amp;p=0', 'psid=10537&amp;p=0&amp;utm_source=secret')
    snapshot = import_snapshot(html, **ARGS)
    assert snapshot['kind'] == 'snapshot'
    assert snapshot['captured_at'] == '2026-10-23T13:00:00+00:00'
    assert len(snapshot['offers']) == 3
    assert {o['starting_course'] for o in snapshot['offers']} == {'Freeway', 'Back 9'}
    serialized = json.dumps(snapshot)
    assert 'personal@' not in serialized and 'utm_' not in serialized
    assert all(o['booking_url'].endswith('p=0') for o in snapshot['offers'])


@pytest.mark.parametrize('override', [
    {'source_url': 'https://example.com/teetimes/searchmatrix'},
    {'source_url': 'https://freeway.quick18.com/teetimes/searchmatrix?teedate=20261025'},
    {'captured_at': datetime(2026, 10, 23)},
    {'captured_at': datetime(2099, 10, 23, tzinfo=timezone.utc)},
    {'day': date(2026, 10, 25)},
])
def test_invalid_provenance_is_rejected(override):
    with pytest.raises(ValueError):
        import_snapshot(HTML, **(ARGS | override))


def test_snapshot_import_does_not_connect_to_database(monkeypatch):
    import golfdb.session
    monkeypatch.setattr(golfdb.session, 'get_engine', lambda *a, **kw: pytest.fail('snapshot accessed database'))
    assert import_snapshot(HTML, **ARGS)['offers']
