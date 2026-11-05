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
