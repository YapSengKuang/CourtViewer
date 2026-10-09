from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CourseOut(BaseModel):
    slug: str
    name: str
    address: str | None
    lat: float | None
    lng: float | None
    holes_options: list[int]
    platform: str
    timezone: str
    booking_url: str | None


class CourseList(BaseModel):
    courses: list[CourseOut]


class TeeTimeOut(BaseModel):
    course_name: str
    address: str | None
    lat: float | None
    lng: float | None
    timezone: str
    holes: int
    price_per_player: Decimal
    currency: str
    starts_at: datetime
    starts_at_local: datetime
    spots_available: int
    booking_url: str
    scraped_at: datetime


class TeeTimeList(BaseModel):
    tee_times: list[TeeTimeOut]


class CourseHealth(BaseModel):
    slug: str
    name: str
    last_success_at: datetime | None
    last_item_count: int | None
    last_error: str | None


class HealthList(BaseModel):
    courses: list[CourseHealth]
