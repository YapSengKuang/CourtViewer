# Freeway delivery sprints

Planned 24 October 2026, Australia/Melbourne. Delivery update: **F1 engineering delivery published; F2 daily search enabled with open acceptance gaps**. See [delivery evidence](FREEWAY_DELIVERY_STATUS.md). The original planned tasks below are retained as acceptance criteria. This is the current delivery sequence for Freeway and supersedes the original sprint calendar and earlier efficiency-first ordering. Existing implementation evidence is in [Freeway integration and scaling](FREEWAY_AND_SCALING.md).

## Outcome and milestones

Users must be able to select Freeway, choose a date, time window, party size and holes, see matching tee times on the hosted Golf Booker website, and follow a link to Freeway to book.

Deliver two distinct milestones:

1. **Hosted proof of concept:** display manually captured Freeway times in an explicitly labelled snapshot/demo view. This proves the date filtering and presentation but does not claim current availability.
2. **Refreshed availability:** display accepted, automatically refreshed Freeway results in normal search, with accurate coverage and release-window messaging. Only this completes the live-availability requirement.

Keep Mandalay working throughout. The existing date-specific provider link is a useful fallback, but neither that link nor the snapshot milestone completes refreshed availability.

## Capacity and proposed calendar

Assume one engineer with up to five working days per sprint and an owner available for source-access decisions and acceptance. Each sprint reserves one day for verification, review and fixes. Dates are planning targets, not commitments; confirm working capacity, including local holidays during the week of 2 November. If capacity is lower, move the dates rather than dropping acceptance checks.

| Sprint | Proposed dates | Goal | Release condition |
| --- | --- | --- | --- |
| F1 | 26–30 October 2026 | Freeway snapshot proof of concept on the hosted website | Snapshot isolation, clear capture labels and hosted checks pass |
| F2 | 2–6 November 2026 | Automatically refreshed Freeway date search | Source-access dependency resolved, representative data accepted and integration/deployment checks pass |
| F3 | 9–13 November 2026 | Reliable operation and measured readiness for more courses | 72-hour soak, failure/restore drills and scaling baseline pass |

F1 can proceed using manually supplied page captures. F2's automated collection and release are conditional on an agreed source-access method. If that is unresolved, continue independent F2 UI/schema/fixture work and F3 test tooling, keep the snapshot label, and publish a revised live-availability date. Waiting for a provider response is not engineering effort and has no assumed duration.

## Starting point

- Built locally: candidate Quick18 adapter, disabled Freeway catalog, sanitised two-row fixture, parser regression tests and selected-date provider link.
- Existing candidate handles standard 9/18-hole rates and preserves separate Freeway/Back 9 group identities. Empty/unreleased layouts remain unverified and fail closed.
- Last recorded checks: 58 Python tests passed, 51 database tests skipped; eight frontend tests, lint and TypeScript passed. Production build hit a worker-port restriction; a build-time dependency advisory also needs verification.
- Not done: hosted Freeway deployment, full database validation, snapshot import/view, release-window states, live source acceptance, recurring Freeway collection or soak.

Existing code is a starting asset, not a completed sprint. Task tables below preserve the original plan; current completion and remaining acceptance are recorded in [delivery status](FREEWAY_DELIVERY_STATUS.md).

## F1 — Publish a clearly labelled proof of concept

Goal: demonstrate Freeway times for specific captured dates on the hosted website without presenting old observations as current availability.

| Task | Work and acceptance | Effort | Owner |
| --- | --- | --- | --- |
| F1.1 | Establish a working build/CI environment and dedicated test Postgres. Run database checks without skips; investigate the dependency advisory and fix confirmed relevant issues. Record the deployable artifact and commit. | 1 day | Engineer |
| F1.2 | Add an offline import/validation command for manually saved HTML. Accept explicit source URL, local requested date and actual capture timestamp; strip tracking/personal content; reject mismatched dates, malformed groups and unverified empty layouts. Obtain representative captures for at least two dates. | 1 day | Engineer; owner supplies captures if needed |
| F1.3 | Add a separate Freeway snapshot/demo view with date, time, players and holes filters. Display capture timestamp, timezone and “Snapshot — check current availability on Freeway”. Keep snapshots outside production availability tables/RPC results and ordinary fresh-course counts. Use “Check current times” for provider handoff. | 1.5 days | Engineer |
| F1.4 | Deploy to a preview, verify filtering and mobile/keyboard use, then publish the labelled demo to the live website with a reversible feature flag. Retain the date-link fallback. | 0.5 day | Engineer |
| F1.5 | Compare at least 20 displayed offers against the captured source across two dates; review with the owner and fix defects. Confirm Mandalay is unaffected and rollback works. | 1 day | Engineer + owner |

**Exit:** a public HTTPS URL shows Freeway snapshot times for selectable captured dates. Unsupported dates say “No snapshot captured for this date”, never “sold out”. Historical snapshots can remain in the demo only with conspicuous capture labels; they never bypass the normal 60-minute freshness rule. No collection schedule is enabled by this sprint.

In parallel, the owner establishes a permitted feed or agreed collection method with Freeway/Quick18. The engineer can prepare a concise request describing fields, cadence, caching and booking handoff; sending it is an owner action unless separately authorised. The published robots policy is a crawler instruction, not a technical access barrier or a claim that normal browsing requires permission. Do not treat proof-of-concept status as resolution of that access dependency.

## F2 — Enable refreshed Freeway availability

Goal: include Freeway in normal date search using a verified, repeatable source.

| Task | Work and acceptance | Effort | Depends on |
| --- | --- | --- | --- |
| F2.1 | Adapt the candidate to the agreed feed/transport. Verify weekday/weekend rates, both starting-course identities, capacity and booking links. Capture real verified-empty and unreleased responses; preserve existing data on failures. | 1.5 days | Source access; F1.2 |
| F2.2 | Add per-course release metadata and explicit not-released/empty/unavailable/stale states across storage, bounded read API and UI. Verify the stated 7 pm/eight-day boundary in Melbourne time, including midnight/DST cases. Do not infer a precise release boundary from marketing copy alone. | 1 day | Representative source evidence |
| F2.3 | Add Freeway to the selected launch catalog with its public flag initially off. Seed, collect and validate date queries in staging. Keep one combined matrix request per date where the accepted transport supports it, bounded retries/timeouts and provider limits. | 0.5 day | F2.1–F2.2 |
| F2.4 | Deploy compatible migrations, collector and frontend; complete a hosted collection, compare anonymous search results, then enable Freeway publicly. Preserve the snapshot view's distinct identity or retire it explicitly. | 1 day | Full tests, source acceptance and preview checks |
| F2.5 | Run production smoke checks and rollback/failure checks; owner accepts the working date-search journey. Record deployment and source-parity evidence. | 1 day | F2.4 |

Engineer owns all F2 implementation and verification; owner resolves source access and accepts scope. The one-week estimate assumes the accepted source resembles the captured matrix. A substantially different feed requires re-estimation before committing this sprint's release date.

**Exit:** Freeway appears in the normal course selector; searches return only matching future groups for the chosen local date, time, holes and party size. Freshness and release states are accurate. At least 20 representative source/result pairs across two dates agree. Captured prices are labelled as per-player round prices with final fees confirmed by the provider. No concession price or combined capacity is misrepresented as a standard offer.

A date outside Freeway's verified release window says “Not released yet” where supported by evidence; an ambiguous response says unavailable/unchecked. The overall today-through-day-14 search horizon does not promise Freeway bookings at day +14. All database tests and the static build must pass before enabling the public flag.

## F3 — Prove reliability and prepare for ten-plus courses

Goal: validate the deployed integration, measure bottlenecks and prepare expansion without delaying F2 for a broad rewrite.

| Task | Work and acceptance | Effort | Owner |
| --- | --- | --- | --- |
| F3.1 | Record per-course request, parsing and publication time, partition success, last fresh coverage, rows written and storage growth. Begin the 72-hour soak on the deployed collector version. | 1 day | Engineer |
| F3.2 | Rehearse source outage, changed response, delayed scheduler and verified-empty behaviour. Test independent Freeway disablement, Mandalay continuity and backup restoration in an isolated database. | 1 day | Engineer |
| F3.3 | Benchmark ten-course-equivalent data/workloads using fixtures in staging, not extra traffic to providers. Measure p95 search latency, collection deadline headroom, history growth and query plans. | 1 day | Engineer |
| F3.4 | Document the measured next scaling changes: batch registration, course/date work batches, per-course leases and coordinated per-host throttling. Define the onboarding checklist and update operating/rollback instructions. | 1 day | Engineer |
| F3.5 | Review soak/benchmark evidence, fix release-blocking findings and agree the next course batch. Any material collector change restarts affected soak evidence. | 1 day | Engineer + owner |

**Exit:** at least 95% of scheduled source partitions succeed during the 72-hour soak; at least 95% of enabled coverage is refreshed within 30 minutes; no normal-search slot older than 60 minutes is served. Search target remains p95 below 500 ms on 10,000 slots at ten concurrent clients. Record missed targets honestly and fix or explicitly revise them before claiming readiness. No claim that ten real courses have been accepted follows from a synthetic benchmark.

Start the soak early in F3 so it can run alongside drills and reviews. Do not increase provider request rates or buy infrastructure to force a pass. A full distributed queue or framework migration is outside these sprints unless measurements establish the need and the scope is revised.

## Release and rollback checklist

- Preview and live checks cover selected dates, 9/18 holes, 1–4 players, time windows, pagination, separate starting tees, provider links and mobile layout.
- Snapshot data stays isolated and labelled. Normal results retain future-only and freshness constraints; unknown responses cannot erase valid availability.
- Public RPC grants remain bounded; collector credentials never enter the frontend. Include a database backup and compatible migration/rollback procedure in the release artifact.
- Disable Freeway independently by removing it from scheduled collection and switching its public flag off. Keep Mandalay enabled. Revert the frontend if needed; do not blindly downgrade a schema used by an active collector.
- Record commit, migration revision, deployed URL, test results, source capture times, collection outcome, operator and rollback steps for each release. A local code change is not a deployment.

## Immediate next task

Review the published F1 demo and finish the F2 acceptance gaps in [delivery status](FREEWAY_DELIVERY_STATUS.md), especially real empty/unreleased response evidence and release timing. Daily collection is enabled under the owner-confirmed agreement; do not exceed the agreed cadence or relax freshness.
