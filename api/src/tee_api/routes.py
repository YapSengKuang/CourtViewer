from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from golfdb.models import Course, TeeTime
from tee_api.deps import get_now, get_session
from tee_api.schemas import CourseHealth, CourseList, CourseOut, HealthList, TeeTimeList, TeeTimeOut

router = APIRouter(prefix="/api")

FRESH_MINUTES = 60


def _local_bound(timezone_name: str, day: date, clock: time) -> datetime:
    zone = ZoneInfo(timezone_name)
    return datetime(day.year, day.month, day.day, clock.hour, clock.minute, tzinfo=zone)


@router.get("/courses", response_model=CourseList)
def list_courses(session: Session = Depends(get_session)) -> CourseList:
    rows = session.scalars(select(Course).order_by(Course.name)).all()
    return CourseList(
        courses=[
            CourseOut(
                slug=course.slug,
                name=course.name,
                address=course.address,
                lat=course.lat,
                lng=course.lng,
                holes_options=list(course.holes_options),
                platform=course.platform,
                timezone=course.timezone,
                booking_url=course.booking_url,
            )
            for course in rows
        ]
    )


@router.get("/health", response_model=HealthList)
def scrape_health(session: Session = Depends(get_session)) -> HealthList:
    rows = session.scalars(
        select(Course).options(joinedload(Course.scrape_run)).order_by(Course.name)
    ).unique()
    courses: list[CourseHealth] = []
    for course in rows:
        run = course.scrape_run
        courses.append(
            CourseHealth(
                slug=course.slug,
                name=course.name,
                last_success_at=None if run is None else run.last_success_at,
                last_item_count=None if run is None else run.last_item_count,
                last_error=None if run is None else run.last_error,
            )
        )
    return HealthList(courses=courses)


@router.get("/tee-times", response_model=TeeTimeList)
def search_tee_times(
    date: date,
    time_from: time,
    time_to: time,
    holes: int,
    players: int = Query(..., ge=1),
    sort: Literal["starts_at", "price"] = "starts_at",
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
) -> TeeTimeList:
    if holes not in (9, 18):
        raise HTTPException(status_code=422, detail="holes must be 9 or 18")
    if time_from > time_to:
        raise HTTPException(status_code=422, detail="time_from must be at or before time_to")

    courses = session.scalars(select(Course)).all()
    windows = []
    for course in courses:
        start = _local_bound(course.timezone, date, time_from)
        end = _local_bound(course.timezone, date, time_to)
        windows.append(
            and_(
                TeeTime.course_id == course.id,
                TeeTime.starts_at >= start,
                TeeTime.starts_at <= end,
            )
        )
    if not windows:
        return TeeTimeList(tee_times=[])

    fresh_after = now - timedelta(minutes=FRESH_MINUTES)
    statement = (
        select(TeeTime, Course)
        .join(Course, Course.id == TeeTime.course_id)
        .where(TeeTime.holes == holes)
        .where(TeeTime.spots_available >= players)
        .where(TeeTime.scraped_at >= fresh_after)
        .where(or_(*windows))
    )
    if sort == "price":
        statement = statement.order_by(
            TeeTime.price_per_player,
            TeeTime.starts_at,
            Course.name,
            TeeTime.holes,
        )
    else:
        statement = statement.order_by(TeeTime.starts_at, Course.name, TeeTime.holes)

    tee_times: list[TeeTimeOut] = []
    for slot, course in session.execute(statement):
        zone = ZoneInfo(course.timezone)
        tee_times.append(
            TeeTimeOut(
                course_name=course.name,
                address=course.address,
                lat=course.lat,
                lng=course.lng,
                timezone=course.timezone,
                holes=slot.holes,
                price_per_player=slot.price_per_player,
                currency=slot.currency,
                starts_at=slot.starts_at,
                starts_at_local=slot.starts_at.astimezone(zone),
                spots_available=slot.spots_available,
                booking_url=slot.booking_url,
                scraped_at=slot.scraped_at,
            )
        )
    return TeeTimeList(tee_times=tee_times)
