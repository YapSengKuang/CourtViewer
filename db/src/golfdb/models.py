from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Boolean,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    lat: Mapped[float | None] = mapped_column(Double, nullable=True)
    lng: Mapped[float | None] = mapped_column(Double, nullable=True)
    holes_options: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    booking_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))

    tee_times: Mapped[list["TeeTime"]] = relationship(back_populates="course")
    scrape_run: Mapped["ScrapeRun | None"] = relationship(
        back_populates="course",
        uselist=False,
    )

    __table_args__ = (
        UniqueConstraint("slug", name="uq_courses_slug"),
        CheckConstraint(
            "lat IS NULL OR (lat >= -90 AND lat <= 90)",
            name="ck_courses_lat",
        ),
        CheckConstraint(
            "lng IS NULL OR (lng >= -180 AND lng <= 180)",
            name="ck_courses_lng",
        ),
        CheckConstraint(
            "(lat IS NULL) = (lng IS NULL)",
            name="ck_courses_lat_lng_pair",
        ),
    )


class TeeTime(Base):
    __tablename__ = "tee_times"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    holes: Mapped[int] = mapped_column(Integer, nullable=False)
    spots_available: Mapped[int] = mapped_column(Integer, nullable=False)
    price_per_player: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    price_unit: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="per_round",
        server_default=text("'per_round'"),
    )
    booking_url: Mapped[str] = mapped_column(Text, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    course: Mapped[Course] = relationship(back_populates="tee_times")

    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "starts_at",
            "holes",
            name="uq_tee_times_course_start_holes",
        ),
        Index("ix_tee_times_starts_at_course_id", "starts_at", "course_id"),
        CheckConstraint("spots_available >= 0", name="ck_tee_times_spots_nonnegative"),
        CheckConstraint("price_per_player >= 0", name="ck_tee_times_price_nonnegative"),
        CheckConstraint("holes > 0", name="ck_tee_times_holes_positive"),
    )


class ScrapeRun(Base):
    """Current scrape health for one course. One row per course."""

    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_item_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    course: Mapped[Course] = relationship(back_populates="scrape_run")

    __table_args__ = (UniqueConstraint("course_id", name="uq_scrape_runs_course_id"),)
