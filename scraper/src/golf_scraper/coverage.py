"""Explicit source coverage; no item count can imply a complete response."""
from dataclasses import dataclass
from datetime import datetime
from collections.abc import Callable


@dataclass
class Partition:
    course_slug: str
    key: str
    start: datetime
    end: datetime
    status: str = "pending"
    error: str | None = None


class Coverage:
    def __init__(self):
        self.partitions: dict[tuple[str, str], Partition] = {}
        self.on_expect: Callable[[Partition], None] | None = None

    def expect(self, slug: str, key: str, start: datetime, end: datetime) -> Partition:
        if not start.tzinfo or not end.tzinfo or start >= end:
            raise ValueError("invalid partition bounds")
        identity = (slug, key)
        if identity in self.partitions:
            existing = self.partitions[identity]
            if (existing.start, existing.end) != (start, end):
                raise ValueError("partition bounds changed within execution")
            return existing
        partition = Partition(slug, key, start, end)
        self.partitions[identity] = partition
        if self.on_expect:
            self.on_expect(partition)
        return partition

    def complete(self, slug: str, key: str) -> None:
        partition = self.partitions[(slug, key)]
        if partition.status != "failed":
            partition.status = "complete"

    def fail(self, slug: str, key: str, error: str) -> None:
        partition = self.partitions[(slug, key)]
        partition.status = "failed"
        partition.error = error


def fixture_coverage(spider):
    """Synthetic adapters explicitly cover their entire configured window."""
    from golf_scraper.window import scrape_window
    spider.coverage = Coverage()
    for course in spider.courses:
        start, end = scrape_window(course.timezone, spider.now)
        spider.coverage.expect(course.id, 'window', start, end)
