from golf_scraper.run_all import run_all, spider_names


def test_discovers_the_example_platform_spider():
    assert "example_platform" in spider_names()


def test_one_failing_spider_does_not_stop_the_others():
    names = spider_names()
    calls: list[str] = []

    def runner(name: str) -> int:
        calls.append(name)
        if name == names[0]:
            return 1
        return 0

    assert run_all(runner) == 1
    assert calls == names


def test_timed_out_spider_does_not_stop_other_spiders():
    import subprocess
    names = spider_names()
    calls = []

    def runner(name):
        calls.append(name)
        if name == names[0]:
            raise subprocess.TimeoutExpired(name, 120)
        return 0

    assert run_all(runner) == 1
    assert calls == names


def test_run_deadline_prevents_starting_additional_spiders(monkeypatch):
    import importlib
    module = importlib.import_module('golf_scraper.run_all')
    monkeypatch.setattr(module, 'RUN_BUDGET_SECONDS', 1)
    moments = iter([0, 0, 2])
    monkeypatch.setattr(module.time, 'monotonic', lambda: next(moments))
    calls = []
    assert run_all(lambda name: calls.append(name) or 0) == 1
    assert calls == [spider_names()[0]]


def test_subprocess_has_a_hard_timeout(monkeypatch):
    import importlib
    from types import SimpleNamespace
    module = importlib.import_module('golf_scraper.run_all')
    kwargs_seen = []
    monkeypatch.setattr(module, 'collection_outcome', lambda *args, **kwargs: 0)
    monkeypatch.setattr(module.subprocess, 'run', lambda *args, **kwargs:
        kwargs_seen.append(kwargs) or SimpleNamespace(returncode=0))
    assert module.run_spider('miclub', timeout=42) == 0
    assert kwargs_seen[0]['timeout'] == 42


def test_beta_catalog_runs_only_configured_real_adapters(monkeypatch):
    monkeypatch.setenv('COURSES_YAML', 'scraper/courses.beta.yaml')
    assert spider_names() == ['miclub']
