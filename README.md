# Golf tee time aggregator

Search available tee times across several golf courses. Scraping runs on a schedule and writes Postgres. User searches only read the database.

Booking is not handled here. Each result will deep-link to the course's own booking page.

## Layout

| Path | Role |
| --- | --- |
| `db/` | SQLAlchemy models, Alembic migrations, course seed. Shared by the scraper and the API. |
| `scraper/` | Scraper config (`courses.yaml`). Spiders come in a later phase. |
| `api/` | FastAPI app. Routes come in a later phase. |
| `web/` | Next.js app. UI comes in a later phase. |

`db/` sits beside the three app directories because both the scraper and the API use the same schema.

## Phase 1 (this checkout)

- Docker Compose Postgres
- Tables: `courses`, `tee_times`, `scrape_runs`
- `scraper/courses.yaml` holds six stub courses. `booking_url` and platform `params` are empty on purpose until the real sites are inspected.
- `python -m golfdb.seed` upserts that file into `courses` and creates an empty `scrape_runs` row per course. Running it again updates course fields and does not clear scrape health.

Times in `tee_times.starts_at` are UTC (`timestamptz`). Each course stores an IANA `timezone` for interpreting searches and displaying local times.

## Local setup

Requires Python 3.11+ and Docker. macOS `/usr/bin/python3` is often 3.9, which is too old. [uv](https://docs.astral.sh/uv/) can download 3.12 without a Homebrew build:

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e "./db[dev]"

cp .env.example .env   # optional; defaults match this file
docker compose up -d
alembic -c db/alembic.ini upgrade head
python -m golfdb.seed
```

If `python3.12` is already on your PATH, `python3.12 -m venv .venv` and `pip install -e "./db[dev]"` work the same way.

`make up`, `make migrate`, `make seed`, and `make test` wrap the same commands. Activate the virtualenv first.

Postgres listens on `localhost:5432` as database `teetimes`, user `golf`, password `golf`.

## Tests

```bash
cd db && pytest
```

Catalog tests always run. Schema and seed tests talk to Postgres and skip if it is not up.
