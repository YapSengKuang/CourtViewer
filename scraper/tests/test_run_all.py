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
