"""Opt-in public courses and bounded Supabase read RPCs.

Revision ID: 0002_public_search
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_public_search"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

SEARCH_SIGNATURE = "public.golf_search(date,time without time zone,time without time zone,integer,integer,integer,integer)"


def upgrade():
    op.add_column("courses", sa.Column("public_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    # No anonymous table policies: the RPCs are the sole public read surface.
    for table in ("courses", "tee_times", "scrape_runs"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC")
    op.execute("""
CREATE FUNCTION public.golf_search(
    p_date date, p_time_from time, p_time_to time, p_players integer,
    p_holes integer DEFAULT NULL, p_limit integer DEFAULT 100, p_offset integer DEFAULT 0
) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
DECLARE
    result jsonb;
BEGIN
    IF p_date IS NULL OR p_time_from IS NULL OR p_time_to IS NULL
       OR NOT isfinite(p_date) OR p_time_from > p_time_to
       OR p_time_to >= time '24:00'
       OR p_players IS NULL OR p_players NOT BETWEEN 1 AND 4
       OR (p_holes IS NOT NULL AND p_holes NOT IN (9,18))
       OR p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 200
       OR p_offset IS NULL OR p_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Invalid search parameters' USING ERRCODE = '22023';
    END IF;
    IF EXISTS (SELECT 1 FROM public.courses WHERE public_enabled)
       AND NOT EXISTS (
           SELECT 1 FROM public.courses c WHERE c.public_enabled
           AND p_date BETWEEN (CURRENT_TIMESTAMP AT TIME ZONE c.timezone)::date
                          AND (CURRENT_TIMESTAMP AT TIME ZONE c.timezone)::date + 14
       ) THEN
        RAISE EXCEPTION 'Date must be today through day +14 in a supported course timezone'
            USING ERRCODE = '22023';
    END IF;
    SELECT coalesce(jsonb_agg(to_jsonb(matches) - 'slot_id' ORDER BY starts_at, course_name, slot_id), '[]'::jsonb)
      INTO result FROM (
        SELECT t.id AS slot_id, c.slug AS course_slug, c.name AS course_name,
               c.address, c.lat, c.lng, c.timezone, t.holes,
               t.price_per_player::text AS price_per_player, t.currency,
               t.starts_at,
               to_char(t.starts_at AT TIME ZONE c.timezone, 'YYYY-MM-DD"T"HH24:MI:SS') AS starts_at_local,
               t.spots_available, t.booking_url, t.scraped_at
        FROM public.tee_times t JOIN public.courses c ON c.id = t.course_id
        WHERE c.public_enabled
          AND p_date BETWEEN (CURRENT_TIMESTAMP AT TIME ZONE c.timezone)::date
                         AND (CURRENT_TIMESTAMP AT TIME ZONE c.timezone)::date + 14
          AND t.starts_at >= (p_date + p_time_from) AT TIME ZONE c.timezone
          AND t.starts_at <= (p_date + p_time_to) AT TIME ZONE c.timezone
          AND t.starts_at > CURRENT_TIMESTAMP
          AND t.scraped_at >= CURRENT_TIMESTAMP - interval '60 minutes'
          AND t.scraped_at <= CURRENT_TIMESTAMP
          AND t.spots_available >= p_players
          AND (p_holes IS NULL OR t.holes = p_holes)
          AND t.booking_url LIKE 'https://%'
        ORDER BY t.starts_at, c.name, t.id
        LIMIT p_limit OFFSET p_offset
      ) matches;
    RETURN jsonb_build_object('tee_times', result, 'limit', p_limit, 'offset', p_offset);
END;
$$;
""")
    op.execute("""
CREATE FUNCTION public.golf_health() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
    SELECT jsonb_build_object('courses', coalesce(jsonb_agg(
        jsonb_build_object('slug', c.slug, 'name', c.name,
                          'last_success_at', r.last_success_at,
                          'last_item_count', r.last_item_count,
                          'last_error', CASE WHEN r.last_error IS NOT NULL THEN 'Source temporarily unavailable' END)
        ORDER BY c.name), '[]'::jsonb))
    FROM public.courses c LEFT JOIN public.scrape_runs r ON r.course_id = c.id
    WHERE c.public_enabled;
$$;
""")
    for signature in (SEARCH_SIGNATURE, "public.golf_health()"):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    # Supabase supplies anon/authenticated; plain Postgres need not have them.
    op.execute(f"""
DO $$
DECLARE role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON public.courses, public.tee_times, public.scrape_runs FROM %I', role_name);
            EXECUTE format('REVOKE ALL ON FUNCTION {SEARCH_SIGNATURE} FROM %I', role_name);
            EXECUTE format('REVOKE ALL ON FUNCTION public.golf_health() FROM %I', role_name);
        END IF;
    END LOOP;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        GRANT USAGE ON SCHEMA public TO anon;
        GRANT EXECUTE ON FUNCTION {SEARCH_SIGNATURE} TO anon;
        GRANT EXECUTE ON FUNCTION public.golf_health() TO anon;
    END IF;
END $$;
""")


def downgrade():
    op.execute(f"DROP FUNCTION {SEARCH_SIGNATURE}")
    op.execute("DROP FUNCTION public.golf_health()")
    # Keep RLS/revocations: downgrade must not accidentally expose cached data.
    op.drop_column("courses", "public_enabled")
