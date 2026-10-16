# Option 4 — database search prototype and setup

Status: the hosted Free project `icrmnklkrmskooeuemjg` is provisioned in Sydney and the public static frontend is deployed at https://golf-booker-beta.pages.dev. Anonymous RPC/table-denial checks pass. Mandalay is enabled after complete hosted collection; Morack remains disabled. Current evidence and remaining operational/billing checks are in [Sprint 3 status](../SPRINT_3_STATUS.md).

## Deploy the database

Use a Supabase **Free** organization/project. Set a private `DATABASE_URL` for the migration operator and scraper using a suitable direct/session connection from Supabase (SQLAlchemy `postgresql+psycopg://...`). Never place it in frontend variables or source control. Run:

```sh
alembic -c db/alembic.ini upgrade head
python -m golfdb.seed
```

Migration `0002_public_search` enables RLS on the three application tables, revokes public/anonymous/authenticated direct access and removes implicit PUBLIC execution from the two new functions. On Supabase it grants only `anon` execution of `golf_search` and `golf_health`. Existing unrelated database functions, schemas and Supabase default privileges are outside this migration; inspect the complete exposed Data API surface before launch. Do not run anonymous visitors as a privileged database user.

The functions use SECURITY DEFINER for their fixed read queries, a fixed empty search path and explicit `public` table names. Their owner must remain a trusted migration identity. Never add dynamic SQL or caller-controlled SQL identifiers to them. New helper functions need explicit grant review: PostgreSQL commonly grants function execution to PUBLIC by default.

All existing/new courses have `public_enabled = false` by default. Re-seeding leaves this operator-managed flag unchanged. This keeps test courses and unverified sources out of public search and health even if previously seeded. Run the production catalog preflight on a curated real-source catalog before onboarding, then enable each course only after source/data correctness verification:

```sql
-- Example only: run after verifying this course is launch-ready.
UPDATE public.courses SET public_enabled = true WHERE slug = 'club-mandalay';
```

Do not enable any source while bookable-group identity or reconciliation release blockers remain. No production course was enabled by the implementation.

## Configure the frontend

Set these public build variables in Cloudflare Pages (and rebuild when changing them):

```text
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLIC_PUBLISHABLE_KEY
```

Use a Supabase **publishable** key, never a secret/service-role key. The client sends it in `apikey` without using it as a bearer token. It calls `POST /rest/v1/rpc/golf_search` and `golf_health` directly. With neither variable set, the local FastAPI development contract remains available; with only one set, requests fail rather than fall back to localhost. Confirm the Pages build environment has both before deployment.

Search JSON arguments: `p_date` (ISO date), `p_time_from`/`p_time_to` (local clocks), `p_players` (1–4), optional `p_holes` (9/18/null), `p_limit` (1–200) and `p_offset` (0–10000). Results contain `tee_times`, `limit` and `offset`; default order is start time, course name and slot ID. Prices are decimal strings. `starts_at` is an absolute timestamp; `starts_at_local` is a course-local wall-clock string accompanied by IANA `timezone`, not an offset-bearing timestamp. Do not parse that local string in the browser timezone.

The prototype excludes disabled courses, past slots, slots older than 60 minutes, future observation timestamps, insufficient capacity, non-HTTPS booking links and dates outside local today through +14. Inputs outside bounds raise SQLSTATE `22023`. A date outside all enabled course horizons is rejected; courses with a different local date are individually excluded when their horizon does not contain the requested date. No enabled courses returns an empty dataset. Health exposes a generic error message rather than raw scraper details.

The deployed Sprint 3 web uses `golf_search_v2`, server-side sorting, course selection, 100-row pages and date partition coverage, described below. Health is still a course-level summary, not proof of full date coverage. Slot cards use the slot's own observation time.

## Cost controls and emergency stop

Free plans/provider blocking are the billing boundary. The query limits cap response size, not total traffic. The hosted anonymous role now has `statement_timeout=3s` and `lock_timeout=1s`, confirmed in role configuration; dedicated slow-query cancellation verification remains pending. No request-rate limit is configured. Browser timeouts do not cancel database work reliably. Public direct API traffic bypasses UI throttling, so monitor quotas and test the disable procedure.

Disable the complete public search surface with a trusted database connection:

```sql
REVOKE EXECUTE ON FUNCTION public.golf_search(date,time,time,integer,integer,integer,integer) FROM anon;
REVOKE EXECUTE ON FUNCTION public.golf_health() FROM anon;
```

This takes effect for subsequent permission checks; it does not cancel already running queries. Also ensure no inherited/PUBLIC grants restore access. Re-grant those exact EXECUTE permissions after recovery; never grant table writes as a shortcut. To disable only one source, set its `public_enabled` flag false. A migration downgrade preserves RLS/revocations intentionally rather than reopening access.

Before launch: verify actual anonymous HTTP calls, table read/write denial, invalid-parameter responses, statement timeout, total API exposure, public-key-only configuration, Free billing state and quota alerts. Measure scrape runtime and database egress on the real sources. The remaining release blockers are tracked in [Sprint 1 status](../SPRINT_1_STATUS.md).

Primary references: [Supabase database functions](https://supabase.com/docs/guides/database/functions), [securing the Data API](https://supabase.com/docs/guides/api/securing-your-api).

## Sprint 3 API update

Apply migration `0004_beta_search` before publishing the new frontend. It calls `golf_search_v2` with the previous arguments plus `p_sort` (`starts_at` or `price`) and optional `p_course_slug`. Responses add `has_more` and sanitised per-course date `coverage`; the default client page is 100 rows. `golf_courses` supplies enabled-course names, timezone and inclusive local date bounds. `golf_coverage` is an internal helper with no public execute grant. The v1 RPC remains for older clients.

Emergency public disable must now also revoke:

```sql
REVOKE EXECUTE ON FUNCTION public.golf_search_v2(date,time,time,integer,integer,integer,integer,text,text) FROM anon;
REVOKE EXECUTE ON FUNCTION public.golf_courses() FROM anon;
```

Apply these in addition to the v1 search/health revocations above; verify no other inherited grants reopen access. Review/verify all four public entry points on the actual hosted instance before enabling courses. Nothing in this migration changes provider billing or rate-limit settings.
