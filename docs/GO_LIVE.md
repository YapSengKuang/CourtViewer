# Seven-course launch

The local app is the reference for the new calendar. The live architecture is:
Python scheduled worker → PostgreSQL → Supabase read RPCs → static Next.js on
Cloudflare Pages. Public searches never start collection.

## Step 1: publish collected observations

`scraper/courses.live.yaml` contains only the seven verified MiClub courses.
`python -m golf_scraper.hosted` collects today through day +14 by default, using
three parallel hosts and serial, robots-aware requests within each host. It
publishes through the existing transactional pipeline rather than importing
potentially stale JSON files. All expected date/fee partitions are durable before
source requests. Verified-empty partitions clear old offers; failed partitions
retain original rows and observation timestamps. Database-backed cooldowns and
the global advisory lock coordinate local/legacy/hosted workers. Courses must be
seeded first; public enablement remains separate from collection.

Run once with the existing private `DATABASE_URL` (never a frontend variable):

```sh
COURSES_YAML=scraper/courses.live.yaml python -m golfdb.seed
python -m golf_scraper.hosted --days 15
```

No blocked sources or Freeway are included. Freeway keeps its isolated daily
collector and database guard.

## Remaining launch steps

2. Hosted API parity: supported holes, date/fee coverage, timestamps and existing
   24-hour observation-window work must match the local preview.
3. Schedule the new worker every 15 minutes on the default GitHub branch. Keep
   the operator stop switch, global lock and independent daily Freeway schedule.
4. Begin a 72-hour observation period. Record run durations, requested versus
   verified scopes, source failures, freshness and public HTTP checks. This period
   cannot be marked complete when the schedule is merely enabled.
5. Deploy the static calendar as a preview for online testing, then promote it
   after acceptance. Keep the previous deployment available for rollback.

The website's Refresh button rereads stored results. It does not start scraping.
Scheduled check times are targets; observation timestamps show actual data age.

## Step 2: calendar API

Migrations `0006_observation_window` and `0007_round_calendar` carry forward the
existing 24-hour observation window and add per-partition supported holes.
`golf_courses` returns `holes_options`; the calendar calls the bounded
`golf_search_v3` RPC. Its private coverage helper considers only the selected
hole option, including verified-empty sheets, and unsupported options remain
explicit. Failed terminal scopes hide retained diagnostic offers; pending work
does not erase the last successful snapshot. Existing v1/v2 RPCs remain for old
clients. No direct anonymous table permissions are added.

The complete Python suite passed against dedicated PostgreSQL: 191 tests with
no skips. Frontend transport/helper tests: 23 passed. A root pytest configuration
uses importlib discovery so the API and scraper's `test_local.py` modules can
both run in CI.

## Step 3: hosted schedule

`collect.yml` runs the seven-course publisher at minutes 07, 22, 37 and 52, using
`GOLF_DATABASE_URL` from GitHub secrets. An administrator seeds metadata once;
the restricted scraper account cannot modify course metadata or public flags.
Neither manual nor scheduled jobs reseed or migrate. An explicit curated catalog
preflight precedes collection. `GOLF_COLLECTION_ENABLED` remains the stop switch,
and repository visibility must remain public under the existing cost policy.
The shared workflow concurrency group and database advisory lock coordinate the
separate daily Freeway workflow. The job has a 15-minute limit; collection's
source-request budget remains nine minutes. Late or failed runs are recorded as
such, never presented as a confirmed refresh.

CI runs on the launch branch and pull requests. The static build uses the tested
Webpack path, avoiding the existing Turbopack CSS worker failure.

## Step 4: online validation and observation period

The first hosted seven-course collection succeeded on 5 November 2026:
[run 41967387057](https://github.com/YapSengKuang/CourtViewer/actions/runs/41967387057).
All 195 expected date/fee scopes were verified (15 for Morack, 30 for each other
course). Collection started at 04:22:51 UTC and finished at 04:31:20 UTC, about
8 minutes 29 seconds. The job including setup took about nine minutes.
After this verification, the seven course public flags were enabled. The existing
daily Freeway integration remains enabled separately, making eight public rows.

The first public HTTP smoke check passed at 04:37 UTC: today had 104 offers,
tomorrow 779 and day +14 had 357 for two players/either holes. Counts are a
point-in-time observation, not a promise of current inventory. The check verified
pagination identities, course-local dates, prices, capacity, booking hosts,
observation timestamps, hole-specific coverage, invalid-input rejection and
direct anonymous table denial. See `docs/evidence/launch-api-smoke.json`.

`scripts/check_live.py` performs these read-only checks without contacting golf
providers. `verify-live.yml` runs it hourly using public repository variables
`GOLF_SUPABASE_URL` and `GOLF_SUPABASE_PUBLISHABLE_KEY`. It also checks that the
seven regular sources have complete tested-date coverage and observations no
older than 45 minutes. Freeway has its own daily policy and is excluded from
that 45-minute check. Pending collection keeps the previous verified coverage
readable; failed terminal scopes still report failure and hide diagnostic rows.

The 72-hour observation period begins when the updated default-branch schedule
is active. At acceptance review, inspect scheduled run timestamps, durations,
failures/skips, health-check runs and current date rollover. A successful manual
run or deployment is not evidence that 72 hours have elapsed successfully.

## Step 5: website preview and promotion

Preview: https://launch-preview.golf-booker-beta.pages.dev
Initial preview deployment: `a991602f`, built from `1771f66` with the project's
public Supabase URL and publishable key. The static build passed with Webpack.
The previous production frontend remains at https://golf-booker-beta.pages.dev.
Only the preview is updated during the observation period. Production promotion
requires the 72-hour review; no custom domain or paid service is introduced.
Rollback uses the previous Cloudflare Pages deployment; collection can be
stopped independently with `GOLF_COLLECTION_ENABLED=false`.

### Hosted browser acceptance

The preview's starting dropdowns navigated to tomorrow's two-player, 18-hole
calendar and displayed 325 offers across all eight course rows. Bundoora's
6:00 am offer opened details showing A$40, four spaces, the actual observation
time and its HTTPS MiClub booking link. Morack correctly displayed
“18-hole availability isn’t collected for this course.” Switching to today
started the axis at the current 3:39 pm course-local time; future dates retained
the 6:00 am start. These are observed values from 5 November, not fixed fixtures.
Final local regression: 192 Python tests passed against PostgreSQL, none skipped;
23 frontend tests, lint, TypeScript and the Webpack static export passed.
