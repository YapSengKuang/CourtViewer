# Sprint 1 — implementation status

Started 16 October 2026 on `codex/sprint-1`. Planning baseline committed as `3adc776` before branching. Sprint 1 remains in progress; hosting and live-source feasibility are not complete.

## Completed first batch

- Ran the existing Python suites with Postgres. Baseline: 29 passed, one crawl test failed because historical rows were counted as part of a new snapshot. Corrected the assertion to compare the current crawl snapshot without deleting historical data.
- Expanded the shared collection/reconciliation window to 15 local dates: today through day +14 inclusive. Added tests for the last date, exclusion of day +15, local midnight rollover, daylight saving and all 30 Mandalay date/fee-group requests. This changes collection coverage, not a guarantee of provider availability or completed booking.
- Configured Next.js static export for Cloudflare Pages. Removed the build-time Google Fonts dependency and used a local system-font stack. No hosted deployment yet.
- Added offline production catalog preflight: `python -m golfdb.preflight path/to/catalog.yaml`. It rejects synthetic adapters, missing real HTTPS URLs and incomplete MiClub parameters. It is an operator check, not an automatic production seeding/search filter or proof of permission/live reliability.
- Added bounded GitHub CI: Postgres integration checks, frontend lint/build, static output check, read-only repository permissions, obsolete-run cancellation and ten-minute job limits. No scraper schedule, deployments or workflow push has been enabled. CI timeouts alone do not replace provider billing controls.

## Verification

- Python: **39 passed, zero skipped** against local Postgres, with one pre-existing FastAPI/Starlette test-client deprecation warning.
- Frontend lint: passed. TypeScript `tsc --noEmit`: passed.
- Production build: blocked locally, including after elevated retry, by Turbopack CSS processing failing to bind a local port (`Operation not permitted`). Static export is configured but not verified; CI must pass the build and `out/index.html` check before hosting.
- Catalog preflight: correctly fails on the six synthetic courses in the development catalog. Production catalog still needs selection and separate configuration.
- Diff whitespace check: passed.

## Source feasibility register

| Source | Evidence | Next action |
| --- | --- | --- |
| Club Mandalay / MiClub | Real URL and fee-group configuration in repository; parser fixture tests pass. The public calendar URL was reachable through a read-only web check, but returned only navigation; robots could not be fetched through that tool. This does not validate current timesheet availability. | Review access conditions and robots through a suitable network environment; verify timestamped live sheets, public prices, capacity semantics and day +14 release behaviour. |
| Glen Waverley / Golf Booking | Owner supplied https://www.golf-booking.com/en/club/glen-waverley-golf-course. Public course page exposes a tee-time control, but extracted HTML did not contain actual slots. | Inspect read-only booking requests and verify release window, fees and capacity before implementing the adapter. Provider terms restrict reuse of system materials/databases outside permitted use; resolve the applicable access arrangement before enabling scheduled collection. |
| Morack / MiClub | Owner supplied https://morack.miclub.com.au/guests/bookings/ViewPublicCalendar.msp. Public page returned 8-hole and 9-hole products plus a course-works notice. Existing adapter is a reuse candidate, not yet validated against this layout. | Discover actual resource/fee-group parameters without guessing; separate cart products, validate nine-hole sheets, and never relabel eight holes as nine. Keep eight-hole products outside the current 9/18 MVP. |
| Six development stubs | Synthetic examples, not real launch courses. | Retain for tests only; do not deploy stubs. |

Sources checked: [Glen Waverley](https://www.golf-booking.com/en/club/glen-waverley-golf-course), [Golf Booking terms](https://www.golf-booking.com/en/terms), [Morack](https://morack.miclub.com.au/guests/bookings/ViewPublicCalendar.msp), and [Mandalay public calendar](https://mandalay.miclub.com.au/guests/bookings/ViewPublicCalendar.msp?booking_resource_id=3000000), 16 October 2026.

## Next work and external dependencies

1. Owner confirmed Glen Waverley and Morack as the additional investigation sources and said a public repository is acceptable. Record this approval; current visibility has not been changed. Prioritise these alongside Mandalay and validate before enabling them.
2. Complete the two-day option 4 feasibility task: Supabase SQL read RPC prototype with restricted grants, frontend contract, measured scraper minutes and database/egress usage. No Supabase/Cloudflare account is configured in this repository.
3. Verify provider Free status and hard billing controls in the actual accounts before enabling remote jobs. No billing settings have been applied by this batch.
4. Create an approved production catalog with disabled-source handling; current preflight deliberately rejects the development list.
5. Resolve bookable-group identity and partition completeness design, retaining the release blockers around combined tee capacities and valid empty sheets. These remain Sprint 2 implementation work.

Do not describe Sprint 1 as complete until live-source feasibility, quota evidence, production build and owner decisions have been recorded.

Morack and Glen Waverley robots URLs could not be retrieved by the web inspection tool; no robots/access approval is inferred. Web extraction can be cached, so live day +14 availability remains unverified.

## Second implementation batch — Supabase search prototype

- Added Alembic `0002_public_search` and the operator-managed `courses.public_enabled` flag, defaulting false without changing existing course visibility in the legacy development API. Production RPCs return only explicitly enabled courses; seeds do not override this flag.
- Added `golf_search` and sanitised `golf_health` JSON RPCs. The search validates inputs, enforces inclusive day +14 per-course local dates, filters freshness/future starts/capacity, and bounds responses and offset. It returns an ordered time subset; complete pagination/price ordering and partition-level coverage remain follow-up work.
- Enabled RLS on application tables, removed PUBLIC function execution and anonymous/authenticated direct table access, and granted only the two explicit RPCs to Supabase's anonymous role when that role exists. Verified a restricted test role can call search but cannot read or modify application tables. No courses were publicly enabled.
- Added frontend Supabase publishable-key configuration, generic errors, a ten-second client request timeout, bounded search requests and checks against accidental localhost fallback for incomplete configuration. Retained local FastAPI mode. Cards use slot observation age and price-per-player/round labels; older search requests cannot overwrite a newer submission. Incomplete/unknown course health and result truncation are disclosed.
- Added [setup, permission review and emergency-disable instructions](operations/SUPABASE_SETUP.md), an example frontend environment file and client contract tests in CI.

Verification: **56 Python tests passed, zero skipped**, and **four frontend client tests passed**; lint, TypeScript and diff checks passed. Production build was retried and remains blocked by the same local Turbopack CSS-worker port-binding permission error. No successful static artifact or live Supabase/PostgREST HTTP test is claimed. Supabase timeout/quota controls and provider billing settings have not been applied.

Next: verify hosted RPC integration and total API exposure, configure anonymous query timeout and usage limits, complete production source parameters/live fixtures, measure source/runtime/egress costs, and resolve the static build gate in an environment permitting the required build processes. The source identity and safe partition reconciliation blockers remain prerequisites to enabling production data. Sprint 1 remains in progress.

## Owner verification and transition to Sprint 2

The owner subsequently ran the static build successfully in ordinary macOS Terminal with Node 24.12.0: compilation, TypeScript, static-page generation and `out/index.html` checks passed. The exported files were served locally on port 8080. This resolves the project static-build gate in that environment; the agent's restricted process environment remains a separate limitation. The reported npm audit output contains five high-severity findings pending triage.

Sprint 1 changes were merged and pushed to `main` at the owner's request. Unfinished hosted/source/billing feasibility items carry forward explicitly; the merge does not mark those acceptance criteria complete. Work continues in [Sprint 2](SPRINT_2_STATUS.md).
