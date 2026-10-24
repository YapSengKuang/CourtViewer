from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import delete

from golfdb.catalog import load_catalog
from golfdb.models import ScrapeExecution
from golf_scraper.daily_freeway import MARKER, collect_once
from golf_scraper.run_all import run_locked


def test_daily_attempt_survives_failure_and_uses_melbourne_calendar(postgres, monkeypatch):
    import golf_scraper.daily_freeway as module
    catalog = load_catalog(Path(__file__).parents[1] / 'courses.freeway.yaml')
    catalog.courses[0].params['collection_enabled'] = True
    monkeypatch.setattr(module, 'load_catalog', lambda: catalog)
    with postgres.begin() as connection:
        connection.execute(delete(ScrapeExecution).where(ScrapeExecution.spider == MARKER))
    calls = []
    def attempt():
        calls.append('attempt')
        assert __import__('os').environ.get('FREEWAY_DAILY_ATTEMPT_ID')
        return 1
    def run(at):
        return run_locked(lambda: collect_once(postgres, attempt, now=datetime.fromisoformat(at)), engine=postgres)
    try:
        # DST: Melbourne midnight is 13:00 UTC, not UTC midnight.
        assert run('2030-10-24T12:59:00+00:00') == 1
        assert run('2030-10-24T12:59:30+00:00') == 0
        assert run('2030-10-24T13:00:00+00:00') == 1
        assert len(calls) == 2
    finally:
        with postgres.begin() as connection:
            connection.execute(delete(ScrapeExecution).where(ScrapeExecution.spider == MARKER))


def test_direct_spider_cannot_use_daily_agreement(postgres, monkeypatch):
    import golf_scraper.spiders.quick18 as module
    catalog = load_catalog(Path(__file__).parents[1] / 'courses.freeway.yaml')
    catalog.courses[0].params['collection_enabled'] = True
    monkeypatch.setattr(module, 'load_catalog', lambda: catalog)
    # No marker means failure before any network activity.
    monkeypatch.delenv('FREEWAY_DAILY_ATTEMPT_ID', raising=False)
    with pytest.raises(ValueError, match='guarded daily runner'):
        module.Quick18Spider(now=datetime.now(timezone.utc))


def test_guarded_attempt_allows_only_agreed_matrix_requests(postgres, monkeypatch):
    import golf_scraper.daily_freeway as daily
    import golf_scraper.spiders.quick18 as adapter
    catalog = load_catalog(Path(__file__).parents[1] / 'courses.freeway-live.yaml')
    monkeypatch.setattr(daily, 'load_catalog', lambda: catalog)
    monkeypatch.setattr(adapter, 'load_catalog', lambda: catalog)
    def inspect_requests():
        requests = list(adapter.Quick18Spider().iter_requests())
        assert len(requests) == 15
        assert all(r.url.startswith('https://freeway.quick18.com/teetimes/searchmatrix?teedate=') for r in requests)
        assert all(r.meta['dont_obey_robotstxt'] and r.meta['dont_retry'] for r in requests)
        return 0
    try:
        assert run_locked(lambda: collect_once(postgres, inspect_requests), engine=postgres) == 0
    finally:
        with postgres.begin() as connection:
            connection.execute(delete(ScrapeExecution).where(ScrapeExecution.spider == MARKER))
