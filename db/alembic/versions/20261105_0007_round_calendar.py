"""Hole-specific coverage and supported-round metadata for the calendar."""
from alembic import op
import sqlalchemy as sa

revision = '0007_round_calendar'
down_revision = '0006_observation_window'
branch_labels = None
depends_on = None


def definition(signature):
    return op.get_bind().scalar(sa.text('SELECT pg_get_functiondef(CAST(:signature AS regprocedure))'), {'signature': signature})


def upgrade():
    op.add_column('scrape_partitions', sa.Column('holes', sa.Integer(), nullable=True))
    op.create_check_constraint('ck_partition_holes', 'scrape_partitions', 'holes IS NULL OR holes IN (9,18)')
    courses = definition('public.golf_courses()')
    if "'holes_options'" not in courses:
        courses = courses.replace("'timezone', timezone,", "'timezone', timezone, 'holes_options', holes_options,")
    op.execute(courses)
    coverage = definition('public.golf_coverage(date,text)')
    coverage = coverage.replace('FUNCTION public.golf_coverage(p_date date, p_course_slug text)',
        'FUNCTION public.golf_round_coverage(p_date date, p_course_slug text, p_holes integer)')
    coverage = coverage.replace('WHERE p.course_id = c.id',
        'WHERE p.course_id = c.id AND (p_holes IS NULL OR p.holes IS NULL OR p.holes = p_holes)')
    coverage = coverage.replace('WHERE c.public_enabled',
        'WHERE c.public_enabled AND (p_holes IS NULL OR p_holes = ANY(c.holes_options))')
    if 'FUNCTION public.golf_round_coverage' not in coverage:
        raise RuntimeError('Unexpected coverage signature')
    op.execute(coverage)
    search = definition('public.golf_search_v2(date,time,time,integer,integer,integer,integer,text,text)')
    search = search.replace('FUNCTION public.golf_search_v2(', 'FUNCTION public.golf_search_v3(')
    search = search.replace('public.golf_coverage(p_date, p_course_slug)', 'public.golf_round_coverage(p_date, p_course_slug, p_holes)')
    guard = '''AND t.scraped_at <= CURRENT_TIMESTAMP
          AND coalesce((SELECT p.status
              FROM public.scrape_partitions p JOIN public.scrape_executions e ON e.id = p.execution_id
              WHERE p.course_id = c.id AND p.key = t.source_partition
                AND p.status <> 'pending'
              ORDER BY e.started_at DESC, p.id DESC LIMIT 1), 'complete') IN ('complete','empty')'''
    search = search.replace('AND t.scraped_at <= CURRENT_TIMESTAMP', guard)
    if 'public.golf_round_coverage(p_date, p_course_slug, p_holes)' not in search:
        raise RuntimeError('Unexpected search definition')
    op.execute(search)
    helper = 'public.golf_round_coverage(date,text,integer)'
    api = 'public.golf_search_v3(date,time,time,integer,integer,integer,integer,text,text)'
    for signature in (helper, api):
        op.execute(f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC')
        for role in ('anon', 'authenticated'):
            op.execute(f"""DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                REVOKE ALL ON FUNCTION {signature} FROM {role}; END IF; END $$""")
    op.execute(f"""DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        GRANT EXECUTE ON FUNCTION {api} TO anon; END IF; END $$""")


def downgrade():
    op.execute('DROP FUNCTION public.golf_search_v3(date,time,time,integer,integer,integer,integer,text,text)')
    op.execute('DROP FUNCTION public.golf_round_coverage(date,text,integer)')
    op.drop_constraint('ck_partition_holes', 'scrape_partitions')
    op.drop_column('scrape_partitions', 'holes')
