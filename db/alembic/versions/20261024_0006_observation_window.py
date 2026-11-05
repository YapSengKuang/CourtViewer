"""Serve known future tee times observed within the last 24 hours."""
from alembic import op
import sqlalchemy as sa

revision = '0006_observation_window'
down_revision = '0005_freeway_metadata'
branch_labels = None
depends_on = None

SIGNATURES = (
    'public.golf_search(date,time,time,integer,integer,integer,integer)',
    'public.golf_search_v2(date,time,time,integer,integer,integer,integer,text,text)',
    'public.golf_coverage(date,text)',
)


def replace_window(old, new):
    connection = op.get_bind()
    for signature in SIGNATURES:
        definition = connection.scalar(sa.text('SELECT pg_get_functiondef(CAST(:signature AS regprocedure))'),
                                       {'signature': signature})
        if old not in definition:
            raise RuntimeError(f'Unexpected observation window in {signature}')
        # CREATE OR REPLACE retains signatures, bounded inputs, grants and the
        # private coverage helper's ACL. Future tee-time and timestamp guards stay.
        op.execute(definition.replace(old, new))


def upgrade():
    replace_window("interval '60 minutes'", "interval '24 hours'")
    op.execute("""UPDATE public.courses SET release_note = replace(release_note,
        'Current results expire after 60 minutes.',
        'Showing known slots updated within the last 24 hours.')
        WHERE release_note LIKE '%Current results expire after 60 minutes.%'""")


def downgrade():
    replace_window("interval '24 hours'", "interval '60 minutes'")
    op.execute("""UPDATE public.courses SET release_note = replace(release_note,
        'Showing known slots updated within the last 24 hours.',
        'Current results expire after 60 minutes.')
        WHERE release_note LIKE '%Showing known slots updated within the last 24 hours.%'""")
