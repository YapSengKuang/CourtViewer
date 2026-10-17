SET LOCAL search_path = public, pg_catalog;

-- Fresh-project baseline for Golf Booker. Generated from repository models and verified local migrations.

DO $$ BEGIN IF to_regclass('public.courses') IS NOT NULL THEN
RAISE EXCEPTION 'Fresh project required: courses already exists'; END IF; END $$;


CREATE TABLE courses (
	id SERIAL NOT NULL,
	slug VARCHAR(64) NOT NULL,
	name VARCHAR(200) NOT NULL,
	address TEXT,
	lat DOUBLE PRECISION,
	lng DOUBLE PRECISION,
	holes_options INTEGER[] NOT NULL,
	platform VARCHAR(64) NOT NULL,
	timezone VARCHAR(64) NOT NULL,
	booking_url TEXT,
	public_enabled BOOLEAN DEFAULT false NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_courses_slug UNIQUE (slug),
	CONSTRAINT ck_courses_lat CHECK (lat IS NULL OR (lat >= -90 AND lat <= 90)),
	CONSTRAINT ck_courses_lng CHECK (lng IS NULL OR (lng >= -180 AND lng <= 180)),
	CONSTRAINT ck_courses_lat_lng_pair CHECK ((lat IS NULL) = (lng IS NULL))
)

;

ALTER TABLE public.courses ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.courses FROM PUBLIC, anon, authenticated;


CREATE TABLE scrape_executions (
	id VARCHAR(36) NOT NULL,
	spider VARCHAR(100) NOT NULL,
	started_at TIMESTAMP WITH TIME ZONE NOT NULL,
	finished_at TIMESTAMP WITH TIME ZONE,
	status VARCHAR(20) NOT NULL,
	PRIMARY KEY (id)
)

;

ALTER TABLE public.scrape_executions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.scrape_executions FROM PUBLIC, anon, authenticated;


CREATE TABLE scrape_partitions (
	id SERIAL NOT NULL,
	execution_id VARCHAR(36) NOT NULL,
	course_id INTEGER NOT NULL,
	key VARCHAR(200) NOT NULL,
	window_start TIMESTAMP WITH TIME ZONE NOT NULL,
	window_end TIMESTAMP WITH TIME ZONE NOT NULL,
	status VARCHAR(20) NOT NULL,
	accepted_count INTEGER DEFAULT '0' NOT NULL,
	rejected_count INTEGER DEFAULT '0' NOT NULL,
	error TEXT,
	PRIMARY KEY (id),
	CONSTRAINT uq_execution_partition UNIQUE (execution_id, course_id, key),
	FOREIGN KEY(execution_id) REFERENCES scrape_executions (id) ON DELETE CASCADE,
	FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_partition_course_key ON scrape_partitions (course_id, key);

ALTER TABLE public.scrape_partitions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.scrape_partitions FROM PUBLIC, anon, authenticated;


CREATE TABLE scrape_runs (
	id SERIAL NOT NULL,
	course_id INTEGER NOT NULL,
	last_success_at TIMESTAMP WITH TIME ZONE,
	last_item_count INTEGER,
	last_error TEXT,
	PRIMARY KEY (id),
	CONSTRAINT uq_scrape_runs_course_id UNIQUE (course_id),
	FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE
)

;

ALTER TABLE public.scrape_runs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.scrape_runs FROM PUBLIC, anon, authenticated;


CREATE TABLE tee_times (
	id SERIAL NOT NULL,
	course_id INTEGER NOT NULL,
	starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
	holes INTEGER NOT NULL,
	spots_available INTEGER NOT NULL,
	price_per_player NUMERIC(10, 2) NOT NULL,
	currency VARCHAR(3) NOT NULL,
	price_unit VARCHAR(32) DEFAULT 'per_round' NOT NULL,
	booking_url TEXT NOT NULL,
	scraped_at TIMESTAMP WITH TIME ZONE NOT NULL,
	source_partition VARCHAR(200) DEFAULT 'window' NOT NULL,
	source_slot_key VARCHAR(200) DEFAULT '' NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_tee_times_bookable_group UNIQUE (course_id, starts_at, holes, source_partition, source_slot_key),
	CONSTRAINT ck_tee_times_spots_nonnegative CHECK (spots_available >= 0),
	CONSTRAINT ck_tee_times_price_nonnegative CHECK (price_per_player >= 0),
	CONSTRAINT ck_tee_times_holes_positive CHECK (holes > 0),
	FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_tee_times_starts_at_course_id ON tee_times (starts_at, course_id);

ALTER TABLE public.tee_times ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.tee_times FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION public.golf_search(p_date date, p_time_from time without time zone, p_time_to time without time zone, p_players integer, p_holes integer DEFAULT NULL::integer, p_limit integer DEFAULT 100, p_offset integer DEFAULT 0)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
        SELECT t.id AS slot_id, t.source_partition, t.source_slot_key, c.slug AS course_slug, c.name AS course_name,
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
$function$;

REVOKE ALL ON FUNCTION public.golf_search(date,time,time,integer,integer,integer,integer) FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION public.golf_health()
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
    SELECT jsonb_build_object('courses', coalesce(jsonb_agg(
        jsonb_build_object('slug', c.slug, 'name', c.name,
                          'last_success_at', r.last_success_at,
                          'last_item_count', r.last_item_count,
                          'last_error', CASE WHEN r.last_error IS NOT NULL THEN 'Source temporarily unavailable' END)
        ORDER BY c.name), '[]'::jsonb))
    FROM public.courses c LEFT JOIN public.scrape_runs r ON r.course_id = c.id
    WHERE c.public_enabled;
$function$;

REVOKE ALL ON FUNCTION public.golf_health() FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION public.golf_courses()
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
        SELECT jsonb_build_object('courses', coalesce(jsonb_agg(jsonb_build_object(
            'slug', slug, 'name', name, 'timezone', timezone,
            'date_from', (CURRENT_TIMESTAMP AT TIME ZONE timezone)::date,
            'date_to', (CURRENT_TIMESTAMP AT TIME ZONE timezone)::date + 14
        ) ORDER BY name), '[]'::jsonb)) FROM public.courses WHERE public_enabled;
        $function$;

REVOKE ALL ON FUNCTION public.golf_courses() FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION public.golf_coverage(p_date date, p_course_slug text)
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
        $function$;

REVOKE ALL ON FUNCTION public.golf_coverage(date,text) FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION public.golf_search_v2(p_date date, p_time_from time without time zone, p_time_to time without time zone, p_players integer, p_holes integer DEFAULT NULL::integer, p_limit integer DEFAULT 100, p_offset integer DEFAULT 0, p_sort text DEFAULT 'starts_at'::text, p_course_slug text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
    result jsonb;
BEGIN
    IF p_sort IS NULL OR p_sort NOT IN ('starts_at', 'price') THEN
        RAISE EXCEPTION 'Invalid sort' USING ERRCODE = '22023';
    END IF;
    IF p_course_slug IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.courses WHERE public_enabled AND slug = p_course_slug) THEN
        RAISE EXCEPTION 'Unknown or disabled course' USING ERRCODE = '22023';
    END IF;
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
           SELECT 1 FROM public.courses c WHERE c.public_enabled AND (p_course_slug IS NULL OR c.slug = p_course_slug)
           AND p_date BETWEEN (CURRENT_TIMESTAMP AT TIME ZONE c.timezone)::date
                          AND (CURRENT_TIMESTAMP AT TIME ZONE c.timezone)::date + 14
       ) THEN
        RAISE EXCEPTION 'Date must be today through day +14 in a supported course timezone'
            USING ERRCODE = '22023';
    END IF;
    SELECT coalesce(jsonb_agg(to_jsonb(matches) - 'slot_id' ORDER BY CASE WHEN p_sort = 'price' THEN currency END, CASE WHEN p_sort = 'price' THEN price_per_player::numeric END, starts_at, course_name, slot_id), '[]'::jsonb)
      INTO result FROM (
        SELECT t.id AS slot_id, t.source_partition, t.source_slot_key, c.slug AS course_slug, c.name AS course_name,
               c.address, c.lat, c.lng, c.timezone, t.holes,
               t.price_per_player::text AS price_per_player, t.currency,
               t.starts_at,
               to_char(t.starts_at AT TIME ZONE c.timezone, 'YYYY-MM-DD"T"HH24:MI:SS') AS starts_at_local,
               t.spots_available, t.booking_url, t.scraped_at
        FROM public.tee_times t JOIN public.courses c ON c.id = t.course_id
        WHERE c.public_enabled AND (p_course_slug IS NULL OR c.slug = p_course_slug)
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
        ORDER BY CASE WHEN p_sort = 'price' THEN t.currency END, CASE WHEN p_sort = 'price' THEN t.price_per_player END, t.starts_at, c.name, t.id
        LIMIT (p_limit + 1) OFFSET p_offset
      ) matches;
    RETURN jsonb_build_object(
        'tee_times', coalesce((SELECT jsonb_agg(value ORDER BY ordinality)
            FROM jsonb_array_elements(result) WITH ORDINALITY WHERE ordinality <= p_limit), '[]'::jsonb),
        'has_more', jsonb_array_length(result) > p_limit,
        'limit', p_limit, 'offset', p_offset,
        'coverage', public.golf_coverage(p_date, p_course_slug));
END;
$function$;

REVOKE ALL ON FUNCTION public.golf_search_v2(date,time,time,integer,integer,integer,integer,text,text) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.golf_search(date,time,time,integer,integer,integer,integer) TO anon;

GRANT EXECUTE ON FUNCTION public.golf_health() TO anon;

GRANT EXECUTE ON FUNCTION public.golf_courses() TO anon;

GRANT EXECUTE ON FUNCTION public.golf_search_v2(date,time,time,integer,integer,integer,integer,text,text) TO anon;

GRANT USAGE ON SCHEMA public TO anon;

CREATE TABLE public.alembic_version (version_num varchar(32) PRIMARY KEY);

INSERT INTO public.alembic_version VALUES ('0004_beta_search');

ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.alembic_version FROM PUBLIC, anon, authenticated;
