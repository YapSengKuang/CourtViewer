import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from golfdb.catalog import CUSTOM_PLATFORM, EXAMPLE_PLATFORM, CourseCatalog, load_catalog
from golfdb.session import load_local_env


def test_real_catalog_includes_club_mandalay_and_stubs():
    catalog = load_catalog()
    by_id = {course.id: course for course in catalog.courses}
    mandalay = by_id["club-mandalay"]
    assert mandalay.name == "Club Mandalay"
    assert mandalay.platform == "miclub"
    assert mandalay.timezone == "Australia/Melbourne"
    assert mandalay.holes_options == [9, 18]
    assert mandalay.booking_url == (
        "https://mandalay.miclub.com.au/guests/bookings/ViewPublicCalendar.msp?booking_resource_id=3000000"
    )
    assert mandalay.params["booking_resource_id"] == "3000000"
    assert [group["holes"] for group in mandalay.params["fee_groups"]] == [18, 9]

    stubs = [course for course in catalog.courses if course.id.startswith("stub-")]
    assert [course.id for course in stubs] == [
        "stub-north",
        "stub-south",
        "stub-east",
        "stub-west",
        "stub-ridge",
        "stub-lake",
    ]
    assert all(course.booking_url is None for course in stubs)
    assert all(course.address is None for course in stubs)
    assert all(course.params == {} for course in stubs)
    assert all(course.timezone == "America/Los_Angeles" for course in stubs)

    by_platform: dict[str, int] = {}
    for course in catalog.courses:
        by_platform[course.platform] = by_platform.get(course.platform, 0) + 1
    assert by_platform == {EXAMPLE_PLATFORM: 4, CUSTOM_PLATFORM: 2, "miclub": 1}


def test_rejects_unknown_timezone(tmp_path: Path):
    path = tmp_path / "courses.yaml"
    path.write_text(
        """
courses:
  - id: stub-north
    name: Stub
    holes_options: [18]
    platform: example_platform
    timezone: Not/AZone
    booking_url: null
    params: {}
"""
    )
    with pytest.raises(ValidationError, match="IANA"):
        load_catalog(path)


def test_rejects_lat_without_lng(tmp_path: Path):
    path = tmp_path / "courses.yaml"
    path.write_text(
        """
courses:
  - id: stub-north
    name: Stub
    lat: 37.7
    holes_options: [18]
    platform: example_platform
    timezone: America/Los_Angeles
    params: {}
"""
    )
    with pytest.raises(ValidationError, match="lat and lng"):
        load_catalog(path)


def test_rejects_duplicate_ids():
    payload = {
        "courses": [
            _course("stub-north"),
            _course("stub-north"),
        ]
    }
    with pytest.raises(ValidationError, match="duplicate"):
        CourseCatalog.model_validate(payload)


def test_rejects_booking_url_that_is_not_http():
    payload = {"courses": [_course("stub-north") | {"booking_url": "ftp://files.example"}]}
    with pytest.raises(ValidationError, match="booking_url"):
        CourseCatalog.model_validate(payload)


def test_local_env_does_not_override_existing_variables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql+psycopg://from-file/teetimes\nNEW_SETTING=from-file\n")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://already-set/teetimes")
    monkeypatch.delenv("NEW_SETTING", raising=False)
    load_local_env(env_file)
    assert os.environ["DATABASE_URL"] == "postgresql+psycopg://already-set/teetimes"
    assert os.environ["NEW_SETTING"] == "from-file"


def _course(course_id: str) -> dict:
    return {
        "id": course_id,
        "name": "Stub",
        "holes_options": [9, 18],
        "platform": "example_platform",
        "timezone": "America/Los_Angeles",
        "booking_url": None,
        "params": {},
    }


def test_catalog_environment_path_resolves_from_repo_root(monkeypatch, tmp_path):
    monkeypatch.setenv('COURSES_YAML', 'scraper/courses.beta.yaml')
    monkeypatch.chdir(tmp_path)
    assert [course.id for course in load_catalog().courses] == ['club-mandalay', 'morack']
