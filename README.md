# Golf tee time aggregator

Search available tee times across several golf courses. Scraping runs on a schedule and writes Postgres. User searches only read the database.

Booking is not handled here. Each result will deep-link to the course's own booking page.

## Layout

| Path | Role |
| --- | --- |
| `db/` | SQLAlchemy models, Alembic migrations, course seed. Shared by the scraper and the API. |
| `scraper/` | Scrapy spiders. `example_platform` is a fixture stub; other spiders come later. |
| `api/` | FastAPI search. Reads Postgres only. |
| `web/` | Next.js search page. |

`db/` sits beside the three app directories because both the scraper and the API use the same schema.

## Phase 1

- Docker Compose Postgres
- Tables: `courses`, `tee_times`, `scrape_runs`
- `scraper/courses.yaml` holds six stub courses. `booking_url` and platform `params` are empty on purpose until the real sites are inspected.
- `python -m golfdb.seed` upserts that file into `courses` and creates an empty `scrape_runs` row per course. Running it again updates course fields and does not clear scrape health.

Times in `tee_times.starts_at` are UTC (`timestamptz`). Each course stores an IANA `timezone` for interpreting searches and displaying local times.

## Phase 2

`example_platform` is the only spider. It loops every catalog course with that platform and parses `scraper/tests/fixtures/example_platform.json`. That file is synthetic. The request URL is a non-routable placeholder that never leaves the process. There is no live booking endpoint yet.

The pipeline drops items with a missing start time, a negative price, or a start time in the past. It upserts on `(course_id, starts_at, holes)`. After a course yields at least one item, tee times in the next 14 local days with an older `scraped_at` are deleted. A course that yields nothing, or errors, keeps its existing rows. `scrape_runs` records `last_success_at`, `last_item_count`, and `last_error`.

```bash
uv pip install -e "./scraper[dev]"
cd scraper && scrapy crawl example_platform
```

## Phase 3

Search never triggers a scrape. `GET /api/tee-times` filters in each course's timezone, keeps rows with enough open spots, and drops anything scraped more than 60 minutes ago. Default sort is start time; `sort=price` sorts by price per player. `GET /api/courses` and `GET /api/health` list the catalog and each course's last successful scrape.

```bash
uv pip install -e "./api[dev]"
uvicorn tee_api.main:app --reload --port 8000
```

Omit `holes` to search both 9- and 18-hole times.

## Phase 4

The search page at `web/` asks for a date, time window, holes (9, 18, or any), and a player count. Cards show the course, location, holes, price per player, local start time, spots left, how long ago that course last scraped successfully, and a Book link that opens the course booking URL in a new tab. Sort by time or price. The page has a loading state and an empty state.

```bash
cd web && npm run dev
```

The page calls `http://localhost:8000` unless `NEXT_PUBLIC_API_URL` is set.

## Phase 5

`python -m golf_scraper.run_all` runs each spider in its own process, so one failure does not stop the rest. `scraper/crontab.example` schedules that every 15 minutes. Install it only after editing the absolute path. The same command is what a later Celery beat or Prefect job would call.

`GET /api/health` is the per-course freshness check the page uses for "Updated X min ago".

## Local setup

Requires Python 3.11+ and Docker. macOS `/usr/bin/python3` is often 3.9, which is too old. [uv](https://docs.astral.sh/uv/) can download 3.12 without a Homebrew build:

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e "./db[dev]" -e "./scraper[dev]" -e "./api[dev]"

cp .env.example .env   # optional; defaults match this file
docker compose up -d
alembic -c db/alembic.ini upgrade head
python -m golfdb.seed
```

If `python3.12` is already on your PATH, `python3.12 -m venv .venv` and `pip install -e "./db[dev]" -e "./scraper[dev]" -e "./api[dev]"` work the same way.

`make up`, `make migrate`, `make seed`, `make test`, `make crawl`, `make api`, and `make web` wrap the same commands. Activate the virtualenv first.

Postgres listens on `localhost:5432` as database `teetimes`, user `golf`, password `golf`.

## Tests

```bash
cd db && pytest
cd scraper && pytest
cd api && pytest
```

Catalog, parser, and request-validation tests always run. Schema, seed, pipeline, crawl, and search tests talk to Postgres and skip if it is not up.
