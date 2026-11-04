from datetime import datetime, timezone
import json

from fastapi.testclient import TestClient
import pytest

from tee_api.deps import get_now
from tee_api.local import app

NOW = datetime(2026, 11, 5, 0, tzinfo=timezone.utc)
KEY = '2026-11-06:1115048'
PARAMS = {'date': '2026-11-06', 'time_from': '06:00', 'time_to': '18:00', 'players': 1, 'course_slug': 'morack'}


def offer(key='one', clock='20:00', price='27.00', spots=4):
    return {'course_slug': 'morack', 'source_partition': KEY, 'source_slot_key': key,
        'starts_at': f'2026-11-05T{clock}:00+00:00', 'observed_at': NOW.isoformat(),
        'holes': 9, 'spots_available': spots, 'price_per_player': price, 'currency': 'AUD',
        'booking_url': 'https://morack.miclub.com.au/guests/bookings/ViewPublicTimesheet.msp'}


@pytest.fixture
def local_client(tmp_path, monkeypatch):
    report = {'schema_version': 1, 'courses': {'morack': {
        'name': 'Morack', 'status': 'complete', 'last_success_at': NOW.isoformat(),
        'partitions': {KEY: {'status': 'complete', 'last_success_at': NOW.isoformat(),
                            'tee_times': [offer()]}}}}}
    path = tmp_path / 'tee-times.json'
    path.write_text(json.dumps(report))
    monkeypatch.setenv('GOLF_LOCAL_REPORT', str(path))
    app.dependency_overrides[get_now] = lambda: NOW
    with TestClient(app) as client:
        yield client, report, path
    app.dependency_overrides.clear()


def test_local_json_populates_frontend_contract_without_database(local_client):
    client, _, _ = local_client
    response = client.get('/api/tee-times', params={**PARAMS, 'holes': '9'})
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    result = response.json()
    row = result['tee_times'][0]
    assert row['course_name'] == 'Morack Public Golf Course'
    assert row['starts_at_local'] == '2026-11-06T07:00:00+11:00'
    assert row['price_per_player'] == '27.00'
    assert row['scraped_at'] == NOW.isoformat().replace('+00:00', 'Z')
    assert result['coverage'][0]['status'] == 'complete'
    courses = client.get('/api/courses').json()['courses']
    assert len(courses) == 7
    assert all(c['slug'] not in ['freeway', 'ivanhoe'] for c in courses)
    assert next(c for c in courses if c['slug'] == 'morack')['date_to'] == '2026-11-06'


def test_next_search_reads_newly_written_collector_report(local_client):
    client, report, path = local_client
    assert len(client.get('/api/tee-times', params=PARAMS).json()['tee_times']) == 1
    report['courses']['morack']['partitions'][KEY]['tee_times'].append(offer('two', '21:00', '30.00', 2))
    path.write_text(json.dumps(report))
    assert len(client.get('/api/tee-times', params=PARAMS).json()['tee_times']) == 2


def test_filters_numeric_price_sort_and_pagination(local_client):
    client, report, path = local_client
    report['courses']['morack']['partitions'][KEY]['tee_times'] = [
        offer('one', '20:00', '100.00', 4), offer('two', '21:00', '9.00', 2)]
    path.write_text(json.dumps(report))
    result = client.get('/api/tee-times', params={**PARAMS, 'sort': 'price', 'limit': 1}).json()
    assert result['tee_times'][0]['price_per_player'] == '9.00'
    assert result['has_more'] is True
    next_page = client.get('/api/tee-times', params={**PARAMS, 'sort': 'price', 'limit': 1, 'offset': 1}).json()
    assert next_page['tee_times'][0]['price_per_player'] == '100.00'
    assert next_page['has_more'] is False
    filtered = client.get('/api/tee-times', params={**PARAMS, 'players': 4, 'time_to': '07:00'}).json()
    assert len(filtered['tee_times']) == 1


@pytest.mark.parametrize('state', ['failed', 'stale', 'invalid_scope', 'unsafe_link', 'invalid_timestamp'])
def test_failed_stale_or_invalid_partition_never_exposes_saved_rows(local_client, state):
    client, report, path = local_client
    partition = report['courses']['morack']['partitions'][KEY]
    if state == 'failed':
        partition['status'] = 'failed'
    elif state == 'stale':
        partition['last_success_at'] = '2026-11-03T00:00:00Z'
    elif state == 'invalid_scope':
        partition['tee_times'][0]['source_partition'] = 'another-partition'
    elif state == 'unsafe_link':
        partition['tee_times'][0]['booking_url'] = 'https://unrelated.example/book'
    else:
        partition['tee_times'][0]['observed_at'] = '2026-11-05T01:00:00Z'
    path.write_text(json.dumps(report))
    result = client.get('/api/tee-times', params=PARAMS).json()
    assert result['tee_times'] == []
    assert result['coverage'][0]['status'] == 'incomplete'


def test_empty_unchecked_and_outside_horizon_remain_distinct(local_client):
    client, report, path = local_client
    partition = report['courses']['morack']['partitions'][KEY]
    partition.update(status='empty', tee_times=[])
    path.write_text(json.dumps(report))
    assert client.get('/api/tee-times', params=PARAMS).json()['coverage'][0]['availability_status'] == 'empty'
    unchecked = client.get('/api/tee-times', params={**PARAMS, 'date': '2026-11-07'}).json()
    assert unchecked['coverage'][0]['status'] == 'unchecked'
    outside = client.get('/api/tee-times', params={**PARAMS, 'date': '2026-12-01'}).json()
    assert outside['coverage'][0]['status'] == 'outside_horizon'


@pytest.mark.parametrize('changes', [{'holes': 12}, {'players': 5}, {'course_slug': 'ivanhoe'},
    {'time_from': '18:00', 'time_to': '06:00'}, {'time_from': '06:00+11:00'}])
def test_invalid_queries_are_rejected(local_client, changes):
    client, _, _ = local_client
    assert client.get('/api/tee-times', params={**PARAMS, **changes}).status_code == 422


def test_missing_report_does_not_fall_back_to_hosted_data(local_client):
    client, _, path = local_client
    path.unlink()
    response = client.get('/api/tee-times', params=PARAMS)
    assert response.status_code == 503
    assert 'Run the local collector' in response.json()['detail']
