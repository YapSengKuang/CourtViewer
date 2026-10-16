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
