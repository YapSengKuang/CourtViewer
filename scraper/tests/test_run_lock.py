import pytest

from golf_scraper.run_all import run_locked


def test_database_lock_prevents_overlapping_workers(postgres):
    calls = []

    def outer():
        assert run_locked(lambda: calls.append('overlap') or 0, engine=postgres) == 2
        return 0

    assert run_locked(outer, engine=postgres) == 0
    assert calls == []
    assert run_locked(lambda: calls.append('next') or 0, engine=postgres) == 0
    assert calls == ['next']


def test_database_lock_releases_after_worker_failure(postgres):
    def failure():
        raise RuntimeError('test worker failed')

    with pytest.raises(RuntimeError, match='test worker failed'):
        run_locked(failure, engine=postgres)
    assert run_locked(lambda: 0, engine=postgres) == 0
