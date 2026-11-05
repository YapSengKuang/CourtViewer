"""Keep last verified coverage readable while a new collection is pending."""
from alembic import op
import sqlalchemy as sa

revision = '0008_pending_coverage'
down_revision = '0007_round_calendar'
branch_labels = None
depends_on = None


def change(old, new):
    definition = op.get_bind().scalar(sa.text("SELECT pg_get_functiondef('public.golf_round_coverage(date,text,integer)'::regprocedure)"))
    if old not in definition:
        raise RuntimeError('Unexpected round coverage definition')
    op.execute(definition.replace(old, new))


def upgrade():
    change('WHERE p.course_id = c.id AND (p_holes', "WHERE p.course_id = c.id AND p.status <> 'pending' AND (p_holes")


def downgrade():
    change("WHERE p.course_id = c.id AND p.status <> 'pending' AND (p_holes", 'WHERE p.course_id = c.id AND (p_holes')
