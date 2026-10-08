"""initial courses, tee_times, and scrape_runs tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("lat", sa.Double(), nullable=True),
        sa.Column("lng", sa.Double(), nullable=True),
        sa.Column("holes_options", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("booking_url", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "lat IS NULL OR (lat >= -90 AND lat <= 90)",
            name="ck_courses_lat",
        ),
        sa.CheckConstraint(
            "lng IS NULL OR (lng >= -180 AND lng <= 180)",
            name="ck_courses_lng",
        ),
        sa.CheckConstraint(
            "(lat IS NULL) = (lng IS NULL)",
            name="ck_courses_lat_lng_pair",
        ),
        sa.UniqueConstraint("slug", name="uq_courses_slug"),
    )
    op.create_table(
        "tee_times",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("holes", sa.Integer(), nullable=False),
        sa.Column("spots_available", sa.Integer(), nullable=False),
        sa.Column("price_per_player", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "price_unit",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'per_round'"),
        ),
        sa.Column("booking_url", sa.Text(), nullable=False),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "course_id",
            "starts_at",
            "holes",
            name="uq_tee_times_course_start_holes",
        ),
        sa.CheckConstraint(
            "spots_available >= 0",
            name="ck_tee_times_spots_nonnegative",
        ),
        sa.CheckConstraint(
            "price_per_player >= 0",
            name="ck_tee_times_price_nonnegative",
        ),
        sa.CheckConstraint("holes > 0", name="ck_tee_times_holes_positive"),
    )
    op.create_index(
        "ix_tee_times_starts_at_course_id",
        "tee_times",
        ["starts_at", "course_id"],
    )
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_item_count", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", name="uq_scrape_runs_course_id"),
    )


def downgrade() -> None:
    op.drop_table("scrape_runs")
    op.drop_index("ix_tee_times_starts_at_course_id", table_name="tee_times")
    op.drop_table("tee_times")
    op.drop_table("courses")
