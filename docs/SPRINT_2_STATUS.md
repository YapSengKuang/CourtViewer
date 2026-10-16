# Sprint 2 — availability correctness

Started 16 October 2026 on `codex/sprint-2`, from Sprint 1 commit `c18604a`, merged and pushed to `main` at the owner's request. Sprint 2 is in progress; this is the first implementation batch.

## First batch: bounded scraper execution

- Added a Postgres session advisory lock around `python -m golf_scraper.run_all`. Another CLI worker sharing the same database skips with exit code 2. The lock is held on a dedicated connection and released on completion or exception. A database connection failure fails closed. This requires a direct/session database connection; transaction-pooling endpoints are unsuitable for session advisory locks.
- Added a nine-minute monotonic run budget and a hard subprocess timeout of at most two minutes per spider, reduced to the remaining run budget. A failed/timed-out spider does not prevent later spiders starting while time remains. These bound collection execution, not dependency installation, database connection setup or provider billing.
- Set network request timeout to 20 seconds and bounded retries to two. Retained per-domain serial requests and throttling. No graceful crawl timeout is used: until partition completeness is implemented, closing after partial collection must not be mistaken for a successful complete snapshot.
- Added Sprint 2 to CI branch triggers. No scheduled production collection or deployment was enabled.

The database lock protects CLI workers on the same database while their lock connection remains alive. Direct calls to `run_all`/individual spiders bypass this CLI lock; all scheduled execution must use the CLI. Network loss of the lock connection can release the advisory lock while a child remains active; fencing and partition transactions remain follow-up concerns. Hard-killed worker connections release locks when Postgres detects disconnection.

Verification: **61 Python tests passed, zero skipped**, including actual concurrent database connections, release after worker failure, subprocess timeout propagation and no new spider after budget expiry. One pre-existing test-client deprecation warning remains. Diff check passed.

## Next work

- P06: preserve stable bookable group identity in parsers, schema, pipeline and API; never sum separate tees into a larger party capacity.
- P07: stage and reconcile each verified complete source/date/resource partition, distinguish valid empty sheets, and retain failed/incomplete snapshots without refreshing observation timestamps.
- P08 remaining: report partial course failures independently of process exit status; add durable execution/partition outcomes and lock-loss handling.
- P09: integration coverage for partial failure, valid empty results, safe deletion, migration and rerun behaviour.
- Carryover: live-source fixtures/parameters, hosted Supabase verification, actual Free billing controls and quota measurement remain open.

Sprint 1 static build update: the owner successfully ran `npm run build` in macOS Terminal, confirmed `out/index.html` and served it locally on port 8080. The static build is verified in that user environment; the agent's local port-binding restriction does not establish a project build failure. Public hosting is not yet deployed. The owner also reported npm audit findings; dependency triage remains outstanding and no forced dependency upgrade was performed.

## Availability correctness batch

Implemented locally:

- **P06:** MiClub provider rows remain separate groups. Schema uniqueness includes source partition and provider row key; FastAPI/Supabase responses carry both fields and the frontend uses them in result keys. A four-player search cannot combine two groups of two.
- **P07:** adapters declare expected coverage before fetching. MiClub partitions are course/local-date/fee-group sheets; synthetic fixture adapters explicitly cover their entire configured window. Observations are staged in bounded memory (20,000 unique items per spider), never written as partial availability. Only positively complete partitions are atomically replaced; verified empty partitions remove their own old observations. Failed/missing/malformed/shutdown partitions retain old rows without refreshing timestamps. Course-row locks serialize publication; an older snapshot cannot overwrite a newer completed partition.
- **P08:** durable execution/partition records distinguish running, complete, empty, failed, incomplete, partial, superseded and interrupted outcomes. Expected partitions are committed before responses. The CLI checks these records after each subprocess, rather than treating a zero Scrapy exit status as success. Timeouts mark outstanding coverage incomplete. Publication uses the actual `spider_closed` reason, not the later-populated finish-reason statistic.
- **P09:** regression coverage includes distinct tee capacities, missing/empty/sold-out/malformed pages, response-date mismatch, duplicate conflicts, partial courses, safe deletion boundaries, idempotent reruns, stale-worker rejection, injected rollback failure, shutdown, durable expected coverage and runner outcome reporting.

Verification: **75 Python tests passed with zero skips** on the existing local Postgres database and separately from a fresh disposable database including all migrations. Four frontend tests, lint, TypeScript and diff checks passed. The final validator also rejects missing URL hosts, malformed currencies and unsupported course hole counts. No live collection, hosted schema, provider billing setting or public-course flag was enabled.

The core Sprint 2 availability changes are implemented and locally verified. Production readiness remains conditional on real-source parity/empty-state fixtures, hosted integration and the carryover billing/source work. The generic MiClub `.no-tee-times` marker is a conservative adapter contract tested synthetically; no new live empty-state capture is claimed. Recognised sold-out booking rows also establish empty coverage. Unrecognised empty layouts fail closed.

Operational limits: staging is in memory, not durable observation storage. A killed process loses its staged observations; committed expected coverage remains available for diagnosis. The CLI marks interrupted subprocesses; if the CLI itself is killed, a historical execution may remain `running` and needs overdue-run review. All scheduled workers must use the CLI/direct-or-session connection. Database fencing protects against older completed snapshots, but lock-connection loss is still an operational fault to monitor. Historical execution retention must be configured before production to keep database use bounded.

See [collection operations](operations/COLLECTION.md) for the migration and recovery procedure. The earlier "Next work" list describes the backlog at the start of Sprint 2 and is superseded for P06–P09 by this batch.
