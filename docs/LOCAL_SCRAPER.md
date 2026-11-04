# Local Python tee-time collector

This local research collector reuses the existing MiClub parser and writes JSON.
It does not require PostgreSQL, seed courses, write to hosted services or change hosted
jobs. The catalog enables seven accessible courses, retains the four originally
blocked sources for diagnostics, and lists Freeway's separate daily integration.
Production configuration is unchanged.

## Run

From the repository root, using the existing virtual environment:

```bash
.venv/bin/python -m golf_scraper.local --list
.venv/bin/python -m golf_scraper.local --days 3
.venv/bin/python -m golf_scraper.local --days 3 --watch
```

The first command is offline. The second collects once and exits. The third
keeps collecting every 15 minutes until Ctrl+C. Keep the process and computer
running; sleeping the computer pauses collection. This is an interval from the
first attempt, not the hosted workflow's fixed clock minutes.

Default output: `.local/tee-times.json` (Git-ignored). Inspect it with:

```bash
.venv/bin/python -m json.tool .local/tee-times.json
```

To install into a new Python 3.11+ virtual environment, install `./db` and
`./scraper` as editable packages. There are no new dependencies:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ./db -e ./scraper -e ./api
```

Select courses or dates for a one-off run:

```bash
.venv/bin/python -m golf_scraper.local --course morack --course yarra-bend --days 3
.venv/bin/python -m golf_scraper.local --course morack --date 2026-11-07 --days 1
```

`--date` must be within the next 15 local calendar dates. Omit it for normal use;
the example date will eventually expire. `--watch` always follows the current
course-local date and cannot be combined with `--date`. `--days` accepts 1–15;
the three-day default keeps initial testing small. One-off runs and watch mode
honour the last attempt in the same output file and avoid rechecking before its
15-minute due time. Different output files are independent: use one output and
one scheduling mechanism for regular operation.

## Populate the local frontend

After collecting data, start both the local read API and existing Next.js
frontend from `web/`:

```bash
npm run dev:local
```

Open `http://127.0.0.1:3001`. The helper starts a read-only FastAPI service on
`127.0.0.1:8001`, points the frontend at it, and clears hosted database settings
for this process only. Existing environment files and hosted services are not
changed. Both servers stop with Ctrl+C. The normal `npm run dev` command retains
its existing configuration.

The API reads `.local/tee-times.json` on every request. It lists the seven enabled
courses, supports course/date/time/holes/player filters, numeric price sorting
and pagination, and returns per-course date coverage. Blocked sources and
Freeway's separate daily collector are excluded from this local preview.
Rows from failed partitions, malformed scopes, future observation timestamps,
unsafe booking hosts and observations older than 24 hours are hidden. Missing
or invalid report files return a clear service-unavailable response without
falling back to another data source. No database import is needed.

Keep the collector running in a separate terminal for 15-minute updates:

```bash
.venv/bin/python -m golf_scraper.local --days 3 --watch
```

After collection completes, submit Search again in the frontend. The web helper
does not start the collector automatically or scrape during user searches.
The starting page offers dropdowns for today through day +14, 1–4 players and
9/18/either holes. Submit it to open `/results`, with date choices above a
calendar of time on the horizontal axis and courses on the vertical axis.
Dates without collected data remain selectable and explicitly say “Not checked”.
For the initial 5–7 November 2026 data, choose 6 November to try all courses;
Growling Frog's 5 November sheets were verified empty.

For a different report path, set `GOLF_LOCAL_REPORT` before starting the helper.
For API-only use, run `.venv/bin/python -m uvicorn tee_api.local:app --host 127.0.0.1 --port 8001`
from the repository root.

Frontend acceptance on 5 November 2026: 15 local API tests and 15 frontend tests
passed; frontend lint and TypeScript checks passed. Browser verification showed
seven courses in the picker and Growling Frog's 6 November 18-hole offers for
two players, including A$69 prices, capacities, observation timestamps and
provider booking links. The API tests also verify that replacing the collector's
report changes the next search without a server restart.

## Course status

Inspected 4–5 November 2026, Australia/Melbourne. Public pages and observed
responses are evidence of technical access, not a contractual permission claim.

| Course | Local status | Verified scope / next dependency |
| --- | --- | --- |
| Club Mandalay | Enabled | Existing MiClub adapter, separate 9/18-hole fee groups. |
| Morack | Enabled | The inspected public calendar offers a 9-hole fee group. Midweek $27 and weekend $30 adult labels were observed; do not infer 18-hole availability. |
| Yarra Bend | Enabled | MiClub 9/18-hole fee groups. Observed adult off-peak/peak labels, Friday afternoon 9 holes, and the 9-hole back-nine early-bird offer. Separate slots retain their identities. |
| Northcote | Enabled | MiClub 9/18-hole round groups; weekday adult and weekend 9-hole rates verified. The sampled Saturday 18-hole sheet is explicitly empty. |
| Bundoora Park | Enabled | MiClub 9/18-hole groups; weekday and weekend adult rates verified. Cart bundles, meal packages and twilight products are excluded. |
| Growling Frog | Enabled | MiClub 9/18-hole groups; 18-hole public fees are embedded in HTML popovers, while 9-hole fees are inline. Only the configured adult rate is collected. |
| Melton Valley | Enabled | MiClub 9/18-hole groups; weekday and weekend adult rates verified. Concession and junior products are excluded. |
| Freeway | Separate daily runner | Existing Quick18 integration requires the cross-host database daily guard. Never contact it from this 15-minute collector. |
| Glen Waverley | Access blocked | Direct HTTP returned 403; normal browser exposed the JavaScript search, but a verified accessible tee-time transport is still needed. |
| Malvern Valley | CAPTCHA required | Public calendar enables CAPTCHA. Offers are 2–4-player packages; package totals must not be treated as prices per player. Needs an approved transport and package-aware mapping. |
| Albert Park | Transport unverified | Chronogolf club metadata is accessible. No tee-time endpoint is assumed; its robots policy disallows `/private_api/`. Needs a permitted, verified availability source. |
| Ivanhoe | Login required | Official round-booking link opens ActiveCarrot site 16's login. Needs an approved availability source. Public online booking scope is adult 18-hole rounds. |

Freeway's existing isolated command remains:

```bash
COURSES_YAML=scraper/courses.freeway-live.yaml .venv/bin/python -m golf_scraper.daily_freeway
```

That command requires a configured PostgreSQL database and seeded Freeway course.
Use the same database guard as any other active Freeway collector; a separate
local database cannot coordinate daily access with a hosted collector. This
integration does not run it or alter the existing agreement.

Do not pass `courses.local.yaml` to `run_all`, seed it into production, or merely
flip a blocked source to enabled. An unverified platform has no local adapter;
the collector will fail it explicitly. MiClub calendars are checked for CAPTCHA,
resource identity and expected fee groups before tee sheets are requested.

## Output and reliability

Each course has a collection status. Enabled courses also have:

- `last_attempt_at`, `last_success_at` and `next_scheduled_at` as UTC timestamps.
- `requested_partitions` identifying the course/date/fee groups checked.
- `partitions` containing per-scope status, original observation timestamps,
  offers, and sanitised failure messages.

`generated_at` is report-generation time, not a promise that every observation
is fresh. `next_scheduled_at` is the next eligible attempt, not confirmed
publication. Consumers must inspect each partition's status and timestamps.
Historical rows retained after failure are diagnostic data, not verified current
availability. A blocked source has unknown availability; it is never labelled
sold out and is not given a synthetic successful timestamp.

Only a complete, date-matched response replaces a partition. Verified empty
responses clear the prior partition; failures preserve old rows and timestamps.
The collector excludes only explicitly verified nonstandard fee labels; unknown
prices or changed layouts fail closed. Prices are displayed round rates per
player, not guaranteed checkout totals. Booking remains on the course website.
Growling Frog's fee popover is parsed as inert HTML without executing scripts;
missing popovers, unknown adult labels or conflicting adult prices fail closed.

Requests are serial, at least one second apart per origin, with robots checks,
20-second request timeouts, no retries, bounded response size, same-origin HTTPS
redirects only, and a nine-minute request budget per cycle. Source crawl delays
and request-rate policies can further slow requests. A local file lock prevents
two processes writing the same output. Output replacement is atomic. Restarting
watch mode honours saved due times. No browser sessions or credentials are used.

## Validation

```bash
.venv/bin/python -m pytest scraper/tests -q
```

`scraper/tests/fixtures/local/` contains small sanitised fragments from inspected
public MiClub sheets for 5–7 November 2026. They retain only date, slot ID,
clock time, fee labels/prices and anonymous availability cell states. They contain
no names, booking details, cookies, tokens, scripts from providers, or complete
captured pages. These fragments support parser regression tests; live collection
checks complete responses independently.

Live JSON output is intentionally not committed. The tests cover date mismatch,
known versus unknown rate exclusions, source isolation, saved freshness after
failure, disabled sources making no requests, cooldown, overlapping writers,
robots failures, redirect boundaries and restart scheduling.

Local acceptance on 5 November 2026: a live three-day run (5–7 November)
completed all 15 requested partitions across Mandalay, Morack and Yarra Bend,
returning 100, 186 and 127 offers respectively (413 total at capture time).
The remaining five entries reported their documented access states without
provider requests. All 71 scraper tests passed; 22 PostgreSQL-dependent tests
skipped because PostgreSQL was unavailable. Watch mode started from the saved
report, displayed the remaining interval without re-fetching, and stopped
cleanly with Ctrl+C. No collector was left running by this validation.

Alternative-course acceptance on 5 November 2026: a live three-day run completed
all 24 requested date/fee-group partitions for Northcote (313 offers), Bundoora
Park (438), Growling Frog (193) and Melton Valley (418): 1,362 offers at capture
time. The default report now includes seven enabled courses; their existing
per-course cooldowns still apply. All 93 scraper tests passed, with the same 22
PostgreSQL-dependent tests skipped. Regression coverage includes 9/18-hole
weekday/weekend pricing, Northcote's verified empty Saturday 18-hole sheet,
Growling Frog's two fee layouts, malformed popovers and conflicting adult prices.
