"""Add refresh/release metadata and detailed availability without changing v2 status."""
from alembic import op
import sqlalchemy as sa

revision = '0005_freeway_metadata'
down_revision = '0004_beta_search'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('courses', sa.Column('refresh_interval_minutes', sa.Integer(), nullable=False, server_default='15'))
    op.add_column('courses', sa.Column('release_note', sa.Text(), nullable=True))
    op.create_check_constraint('ck_courses_refresh_positive', 'courses', 'refresh_interval_minutes > 0')
    connection = op.get_bind()
    courses = connection.execute(sa.text("SELECT pg_get_functiondef('public.golf_courses()'::regprocedure)")).scalar_one()
    courses = courses.replace("'timezone', timezone,", "'timezone', timezone, 'refresh_interval_minutes', refresh_interval_minutes, 'release_note', release_note,")
    op.execute(courses)
    coverage = connection.execute(sa.text("SELECT pg_get_functiondef('public.golf_coverage(date,text)'::regprocedure)")).scalar_one()
    coverage = coverage.replace("'expected', coverage.expected", """'availability_status', CASE
              WHEN p_date NOT BETWEEN (CURRENT_TIMESTAMP AT TIME ZONE c.timezone)::date
                  AND (CURRENT_TIMESTAMP AT TIME ZONE c.timezone)::date + 14 THEN 'outside_horizon'
              WHEN coverage.expected = 0 THEN 'unchecked'
              WHEN coverage.fresh = coverage.expected AND coverage.empty_count = coverage.expected THEN 'empty'
              WHEN coverage.fresh = coverage.expected THEN 'available'
              WHEN coverage.failures > 0 THEN 'unavailable'
              WHEN coverage.oldest < CURRENT_TIMESTAMP - interval '60 minutes' THEN 'stale'
              ELSE 'unavailable' END,
            'observed_at', coverage.oldest,
            'refresh_interval_minutes', c.refresh_interval_minutes,
            'release_note', c.release_note,
            'expected', coverage.expected""")
    coverage = coverage.replace('count(*) AS expected,', """count(*) AS expected,
                count(*) FILTER (WHERE latest.status = 'empty') AS empty_count,
                count(*) FILTER (WHERE latest.status NOT IN ('complete','empty')) AS failures,
                min(latest.started_at) AS oldest,""")
    if "'availability_status'" not in coverage or "'refresh_interval_minutes'" not in courses:
        raise RuntimeError('Unexpected previous RPC definition')
    # CREATE OR REPLACE retains existing bounded RPC grants and private helper ACL.
    op.execute(coverage)


def downgrade():
    raise RuntimeError('Forward-only metadata migration: rollback frontend/public flag; do not remove columns used by active collectors')
