import re
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

# Shared booking platform. One spider (added later) covers every course with this value.
# Rename it once the real platform is known. Do not invent request URLs here.
EXAMPLE_PLATFORM = "example_platform"

# Bespoke sites. Each gets spiders/custom_<id>.py in a later phase.
CUSTOM_PLATFORM = "custom"


def repo_root() -> Path:
    """Walk parents until the monorepo root (the directory that holds scraper/)."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "scraper" / "courses.yaml").is_file() and (parent / "docker-compose.yml").is_file():
            return parent
    raise RuntimeError("could not locate the repo root from golfdb")


def default_catalog_path() -> Path:
    return repo_root() / "scraper" / "courses.yaml"


class CourseSpec(BaseModel):
    """One course from courses.yaml.

    `id` is the stable slug. Platform-specific request settings live in `params`
    and stay in the YAML file; spiders read them from there. They are not columns.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    holes_options: list[int]
    platform: str
    timezone: str
    booking_url: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def id_is_slug(cls, value: str) -> str:
        if not SLUG_RE.fullmatch(value):
            raise ValueError("id must be a lowercase slug (letters, numbers, hyphens)")
        return value

    @field_validator("name", "platform", "timezone")
    @classmethod
    def not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("timezone")
    @classmethod
    def timezone_is_iana(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown IANA timezone: {value}") from exc
        return value

    @field_validator("holes_options")
    @classmethod
    def holes_are_positive_and_unique(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("holes_options must not be empty")
        if len(set(value)) != len(value):
            raise ValueError("holes_options must not contain duplicates")
        if any(holes <= 0 for holes in value):
            raise ValueError("holes_options values must be positive")
        return value

    @field_validator("booking_url")
    @classmethod
    def booking_url_is_http(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.startswith(("http://", "https://")):
            raise ValueError("booking_url must start with http:// or https://")
        return value

    @model_validator(mode="after")
    def coordinates_are_a_pair(self) -> "CourseSpec":
        if (self.lat is None) != (self.lng is None):
            raise ValueError("lat and lng must both be set or both be null")
        if self.lat is not None and not -90 <= self.lat <= 90:
            raise ValueError("lat must be between -90 and 90")
        if self.lng is not None and not -180 <= self.lng <= 180:
            raise ValueError("lng must be between -180 and 180")
        return self


class CourseCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    courses: list[CourseSpec]

    @model_validator(mode="after")
    def ids_are_unique(self) -> "CourseCatalog":
        ids = [course.id for course in self.courses]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate course id in catalog")
        return self


def load_catalog(path: Path | None = None) -> CourseCatalog:
    catalog_path = path or default_catalog_path()
    raw = yaml.safe_load(catalog_path.read_text())
    return CourseCatalog.model_validate(raw)
