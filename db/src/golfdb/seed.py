"""Upsert courses from scraper/courses.yaml into Postgres."""

import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from golfdb.catalog import CourseSpec, default_catalog_path, load_catalog, repo_root
from golfdb.models import Course, ScrapeRun
from golfdb.session import load_local_env, session_factory


@dataclass(frozen=True)
class SeedResult:
    inserted: int
    updated: int

    @property
    def total(self) -> int:
        return self.inserted + self.updated


def apply_seed(session: Session, courses: list[CourseSpec]) -> SeedResult:
    """Insert or update each course. Does not delete courses missing from the catalog.

    Also ensures a scrape_runs row exists so health reporting has a place to write.
    Re-seeding does not clear last_success_at, last_item_count, or last_error.
    """
    inserted = 0
    updated = 0
    for spec in courses:
        existing = session.scalar(select(Course).where(Course.slug == spec.id))
        if existing is None:
            course = Course(
                slug=spec.id,
                name=spec.name,
                address=spec.address,
                lat=spec.lat,
                lng=spec.lng,
                holes_options=list(spec.holes_options),
                platform=spec.platform,
                timezone=spec.timezone,
                booking_url=spec.booking_url,
            )
            session.add(course)
            session.flush()
            session.add(ScrapeRun(course_id=course.id))
            inserted += 1
            continue

        existing.name = spec.name
        existing.address = spec.address
        existing.lat = spec.lat
        existing.lng = spec.lng
        existing.holes_options = list(spec.holes_options)
        existing.platform = spec.platform
        existing.timezone = spec.timezone
        existing.booking_url = spec.booking_url
        if existing.scrape_run is None:
            session.add(ScrapeRun(course_id=existing.id))
        updated += 1

    return SeedResult(inserted=inserted, updated=updated)


def catalog_path_from_env() -> Path:
    load_local_env()
    override = os.environ.get("COURSES_YAML")
    if override:
        path = Path(override)
        return path if path.is_absolute() else repo_root() / path
    return default_catalog_path()


def main() -> None:
    path = catalog_path_from_env()
    catalog = load_catalog(path)
    factory = session_factory()
    with factory() as session:
        result = apply_seed(session, catalog.courses)
        session.commit()
    print(
        f"Seeded {result.total} courses from {path} "
        f"({result.inserted} inserted, {result.updated} updated)"
    )


if __name__ == "__main__":
    main()
