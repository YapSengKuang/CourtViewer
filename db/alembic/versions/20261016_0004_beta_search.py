"""Course selection, ordered pages and date-specific source coverage."""
from alembic import op
import sqlalchemy as sa

revision = '0004_beta_search'
down_revision = '0003_partition_identity'
branch_labels = None
depends_on = None

SIGNATURE = 'public.golf_search_v2(date,time,time,integer,integer,integer,integer,text,text)'


def upgrade():
    op.execute('''CREATE FUNCTION public.golf_courses() RETURNS jsonb
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
        SELECT jsonb_build_object('courses', coalesce(jsonb_agg(jsonb_build_object(
            'slug', slug, 'name', name, 'timezone', timezone,
            'date_from', (CURRENT_TIMESTAMP AT TIME ZONE timezone)::date,
            'date_to', (CURRENT_TIMESTAMP AT TIME ZONE timezone)::date + 14
        ) ORDER BY name), '[]'::jsonb)) FROM public.courses WHERE public_enabled;
        $$''')
    op.execute('''CREATE FUNCTION public.golf_coverage(p_date date, p_course_slug text) RETURNS jsonb
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
        SELECT coalesce(jsonb_agg(jsonb_build_object('slug', c.slug, 'name', c.name,
            'status', CASE
              WHEN p_date NOT BETWEEN (CURRENT_TIMESTAMP AT TIME ZONE c.timezone)::date
                  AND (CURRENT_TIMESTAMP AT TIME ZONE c.timezone)::date + 14 THEN 'outside_horizon'
              WHEN coverage.expected = 0 THEN 'unchecked'
              WHEN coverage.fresh = coverage.expected THEN 'complete'
              ELSE 'incomplete' END,
            'expected', coverage.expected, 'checked', coverage.fresh
        ) ORDER BY c.name), '[]'::jsonb)
        FROM public.courses c
        CROSS JOIN LATERAL (
            SELECT count(*) AS expected,
                count(*) FILTER (WHERE latest.status IN ('complete','empty')
                    AND latest.started_at >= CURRENT_TIMESTAMP - interval '60 minutes'
                    AND latest.started_at <= CURRENT_TIMESTAMP) AS fresh
            FROM (
                SELECT DISTINCT ON (p.key) p.key, p.status, e.started_at
                FROM public.scrape_partitions p JOIN public.scrape_executions e ON e.id = p.execution_id
                WHERE p.course_id = c.id
                  AND p.window_start < ((p_date + 1)::timestamp AT TIME ZONE c.timezone)
                  AND p.window_end > (p_date::timestamp AT TIME ZONE c.timezone)
                ORDER BY p.key, e.started_at DESC, p.id DESC
            ) latest
        ) coverage
        WHERE c.public_enabled AND (p_course_slug IS NULL OR c.slug = p_course_slug);
        $$''')
    definition = op.get_bind().execute(sa.text("SELECT pg_get_functiondef('public.golf_search(date,time,time,integer,integer,integer,integer)'::regprocedure)")).scalar_one()
    # Freeze the existing validated contract, keeping the v1 RPC available to old clients.
    definition = definition.replace('FUNCTION public.golf_search(', 'FUNCTION public.golf_search_v2(')
    definition = definition.replace('p_offset integer DEFAULT 0)', "p_offset integer DEFAULT 0, p_sort text DEFAULT 'starts_at', p_course_slug text DEFAULT NULL)")
    if 'p_sort text' not in definition:
        raise RuntimeError('Unexpected search function signature')
    definition = definition.replace('    IF p_date IS NULL', '''    IF p_sort IS NULL OR p_sort NOT IN ('starts_at', 'price') THEN
        RAISE EXCEPTION 'Invalid sort' USING ERRCODE = '22023';
    END IF;
    IF p_course_slug IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.courses WHERE public_enabled AND slug = p_course_slug) THEN
        RAISE EXCEPTION 'Unknown or disabled course' USING ERRCODE = '22023';
    END IF;
    IF p_date IS NULL''')
    definition = definition.replace('WHERE c.public_enabled', 'WHERE c.public_enabled AND (p_course_slug IS NULL OR c.slug = p_course_slug)')
    definition = definition.replace('ORDER BY t.starts_at, c.name, t.id', "ORDER BY CASE WHEN p_sort = 'price' THEN t.currency END, CASE WHEN p_sort = 'price' THEN t.price_per_player END, t.starts_at, c.name, t.id")
    definition = definition.replace('ORDER BY starts_at, course_name, slot_id', "ORDER BY CASE WHEN p_sort = 'price' THEN currency END, CASE WHEN p_sort = 'price' THEN price_per_player::numeric END, starts_at, course_name, slot_id")
    definition = definition.replace('LIMIT p_limit OFFSET p_offset', 'LIMIT (p_limit + 1) OFFSET p_offset')
    definition = definition.replace("RETURN jsonb_build_object('tee_times', result, 'limit', p_limit, 'offset', p_offset);", """RETURN jsonb_build_object(
        'tee_times', coalesce((SELECT jsonb_agg(value ORDER BY ordinality)
            FROM jsonb_array_elements(result) WITH ORDINALITY WHERE ordinality <= p_limit), '[]'::jsonb),
        'has_more', jsonb_array_length(result) > p_limit,
        'limit', p_limit, 'offset', p_offset,
        'coverage', public.golf_coverage(p_date, p_course_slug));""")
    op.execute(definition)
    for signature in (SIGNATURE, 'public.golf_courses()', 'public.golf_coverage(date,text)'):
        op.execute(f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC')
        for role in ('anon', 'authenticated'):
            op.execute(f"""DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                REVOKE ALL ON FUNCTION {signature} FROM {role}; END IF; END $$""")
    op.execute(f'''DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
            GRANT EXECUTE ON FUNCTION {SIGNATURE}, public.golf_courses() TO anon;
        END IF;
    END $$''')


def downgrade():
    op.execute(f'DROP FUNCTION {SIGNATURE}')
    op.execute('DROP FUNCTION public.golf_coverage(date,text)')
    op.execute('DROP FUNCTION public.golf_courses()')
