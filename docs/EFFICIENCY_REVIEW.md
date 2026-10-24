# Repository efficiency review — 24 October 2026

## Scope and conclusion

Reviewed collection, persistence, search SQL, frontend requests, the local API, workflows, tests and planning at commit `d131fd0`. This is a repository review, not a live-service audit or performance benchmark. Hosted timings below are historical evidence from [Sprint 3](SPRINT_3_STATUS.md), not measurements repeated today.

Keep the current architecture: static Next.js → Supabase read functions, with Python collection in GitHub Actions. Prioritise fewer collector database round trips, reproducible installs and fewer redundant client requests. Preserve partition transactions, freshness filtering, provider throttling and worker locking.

An existing [project plan](PROJECT_PLAN.md) and [sprint timeline](TIMELINE_AND_SPRINTS.md) already cover the product. This review supplies their current next-work queue; it does not replace the agreed product scope.

## Prioritised findings

### E1 — Reduce collector database round trips (high)

**Evidence:** `scraper/src/golf_scraper/pipelines.py` commits every `_register()` separately, then every `_publish()`. MiClub declares all expected partitions before requests start. Mandalay's 30 date/fee partitions therefore require 30 registration commits alone. The pipeline also retains course ORM objects across commits; `db/src/golfdb/session.py` uses default session expiration, so subsequent attribute access can require reloads. Publication performs locks, record lookups and newer-snapshot checks per partition.

The 17 October acceptance record reports a two-minute durable execution and 2m36s total job. This suggests investigating publication overhead but does not prove where time is spent.

**Work:** instrument registration, network/parsing and publication separately, including statement/transaction counts. Persist the execution and initially known partitions in one transaction before requests begin; retain durable registration for later-discovered partitions. Cache immutable course IDs/metadata explicitly. Profile inserts before replacing ORM insertion, which may already batch statements. Keep each published partition atomic and retain newer-snapshot checks.

**Done when:** all 30 initial partitions are durable before the first request; interruption, partial failure and verified-empty semantics pass integration tests; before/after query counts and comparable run timings show the benefit. Do not increase provider request concurrency to compensate for database latency.

### E2 — Make scheduled dependency installs reproducible (high)

**Evidence:** `.github/workflows/collect.yml` installs Python packages every run. Python manifests use lower bounds and the repository has no Python dependency lockfile. Scheduled runs can receive new dependencies without a code change and repeatedly perform dependency resolution. The web already uses a committed npm lockfile with `npm ci`.

**Work:** adopt a checked-in Python lock or fully resolved constraints file used by CI and collection. Measure installation time separately. Consider a bounded cache only after measuring the benefit; the workflow deliberately has no cache, so document storage and eviction policy if that changes.

**Done when:** fresh CI and collection environments resolve identical runtime versions; updates pass tests; cold-install and any cache-hit timings are recorded. Preserve job limits, standard runners and the stop switch.

### E3 — Prevent redundant browser searches (medium)

**Evidence:** `web/src/components/search-page.tsx` ignores superseded responses using a request counter, but Search remains enabled and obsolete requests keep running. `web/src/lib/api.ts` has RPC timeouts but no caller cancellation signal or identical-request deduplication; local search/health requests lack timeouts.

**Work:** deduplicate identical in-flight searches, abort superseded requests/on unmount, retain response-counter protection, and apply consistent transport timeouts. Begin with in-flight deduplication. Only add result caching if measurements justify it and freshness is checked again before reuse. Browser cancellation does not guarantee cancellation of SQL already executing.

**Done when:** repeated identical submissions issue one request; new filters supersede old requests; cancellation neither displays an error nor overwrites newer results; pagination retains submitted filters. Add component race/paging tests—the existing six frontend tests exercise the API client only.

### E4 — Measure coverage-query scaling (medium)

**Evidence:** `golf_coverage` in migration `0004_beta_search` joins execution history and selects latest partition records per search. With 96 scheduled runs/day, 30 partitions/run and 30-day retention, Mandalay alone can produce about 86,400 retained partition rows, assuming every run occurs. The existing `(course_id, key)` index does not directly index date-overlap predicates. This is a scaling hypothesis, not a demonstrated slow query.

**Work:** use a disposable database with representative history and 10,000 slots to inspect query plans and benchmark time/price sorts, course filters and later pages. Add an index or current-coverage projection only if measurements warrant it, using a new migration rather than rewriting applied history.

**Done when:** report plans, buffers, latency, storage and added write cost. Reuse the project's p95 <500 ms at 10 concurrent clients target as a measurement goal; verify permissions and result/coverage equivalence after any SQL change.

### E5 — Bound failure-history growth and rehearse recovery (medium)

**Evidence:** `scraper/src/golf_scraper/maintenance.py` preserves interrupted executions indefinitely and stops at 350 MiB before pruning. `run_all.py` marks unfinished executions interrupted. Repeated failures can accumulate records beyond normal retention, and after the storage guard trips automatic pruning cannot run.

**Work:** define bounded retention for reviewed terminal interrupted records and an operator procedure for recovering from the size threshold. Preserve active/uncertain work until ownership is checked. Measure growth and dead tuples from delete/reinsert publication before considering differential writes.

**Done when:** a disposable-database drill proves recovery; active records remain protected; reviewed failure history has finite retention; the stop guard still works. Do not assume row deletion immediately reduces PostgreSQL's reported file size.

### E6 — Reduce development and planning drift (medium)

**Evidence:** `Makefile` tests Python only, while CI also runs frontend tests, lint and build. Database fixtures skip when Postgres is unavailable. Local FastAPI and SQL maintain similar search logic separately; local ordering ends at holes rather than a unique slot ID, leaving tied groups without deterministic ordering. The original plan and calendar predate completed beta work.

**Work:** document one full-check command requiring a dedicated test database and including web checks. Add a unique tie-breaker to local paging and tests with tied groups. Keep FastAPI explicitly development/reference-only unless a second production transport is needed. Separate original estimates from current outstanding work.

**Done when:** one command clearly reports full results and fails on unavailable integration prerequisites; tied results paginate deterministically on an unchanged dataset; tests remain isolated from deployed and development data.

## Next-work sequence

Estimates are provisional engineer effort, not delivery commitments. The engineer owns implementation/evidence; the owner accepts operational readiness and source scope.

| Order | Work | Effort | Completion evidence |
| --- | --- | --- | --- |
| 1 | E6 full-test baseline and E1 instrumentation | 1 day | Database tests without skips; phase timings and query counts |
| 2 | E1 registration/metadata improvements | 1–2 days | Fewer round trips; interruption, empty-sheet and supersession tests pass |
| 3 | E2 locked installs and E3 request handling | 1–2 days | Reproducible environments; deduplication/race/paging tests pass |
| 4 | E4 SQL benchmark and E5 retention/recovery | 1–2 days | Query-plan report; justified optimisations; storage-recovery drill |
| 5 | Outstanding operational gates | 1–2 days plus 72 hours elapsed soak | Coverage/freshness evidence, backup/restore and failure drill, quota/budget review |
| 6 | Morack acceptance, then Glen Waverley feasibility | Re-estimate after source evidence | Verified fixtures/parity before public enablement |

Run the soak after material collector changes. Preserve Mandalay-only scope until follow-up sources pass acceptance. The original three-course target applies to expansion; a deployed website alone does not establish operational acceptance. This review does not justify a framework rewrite, increased source request rate or paid infrastructure.

## Verification performed

- Python: `.venv/bin/python -m pytest db/tests scraper/tests api/tests -q`, explicitly targeting local `teetimes_test`: **37 passed, 51 skipped** because test Postgres was unavailable. Database-dependent migrations, reconciliation, locks and search remain unverified by this run. One FastAPI test-client dependency deprecation warning appeared.
- Frontend: `npm test`: **6 passed**; `npm run lint`: **passed**.
- No application code, schema, deployed configuration or provider account settings changed. Proposed optimisations remain unimplemented and unbenchmarked. Historical full-suite and hosted results do not replace a new integration baseline.
