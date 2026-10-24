# Golf Booker — timeline and proposed sprints

## Current delivery plan — Freeway

Use the [Freeway sprint plan](FREEWAY_SPRINTS.md) for the current backlog, ownership, dependencies and acceptance criteria. These one-week sprints replace the original future calendar below; dates assume available engineering capacity and are provisional.

| Sprint | Target dates | Deliverable |
| --- | --- | --- |
| F1 | 26–30 October 2026 | Labelled Freeway snapshot proof of concept on the hosted website |
| F2 | 2–6 November 2026 | Refreshed Freeway availability in normal date search, conditional on accepted source access |
| F3 | 9–13 November 2026 | Operational soak, recovery checks and measured ten-course scaling baseline |

The snapshot demo is not refreshed availability. If the source dependency remains unresolved, retain clear snapshot labels and re-estimate F2's live release. Efficiency work is prioritised where it supports these milestones; Morack/Glen Waverley remain behind Freeway.

## Historical calendar — superseded

The calendar and sprint breakdown below preserve the original estimates. Much of Sprints 1–3 and beta hosting was implemented by 17 October; see [Sprint 3 status](SPRINT_3_STATUS.md) for recorded evidence.

**Selected-stack update:** use option 4 (Cloudflare Pages static frontend, Supabase SQL API/Postgres, Python scraping in GitHub Actions). Sprint 1 includes the two-day free-tier feasibility task and billing-control verification described in the project plan. P11 delivers bounded SQL search RPCs instead of extending the production FastAPI service; P12 updates the frontend client; P14 configures Pages, Supabase and Actions with zero-spend controls. Validate quota exhaustion and service recovery in P16. Re-estimate after the feasibility task; dates below remain provisional.

Proposed as of Friday 16 October 2026, Australia/Melbourne. Assumes one full-time engineer, weekly product-owner decisions and part-time QA/design review. Start Monday 19 October; four two-week sprints provide an eight-week MVP window. Dates are estimates, conditional on source access and the website list being confirmed in Sprint 1. Public holidays, leave and provider delays require re-estimation.

| Phase | Dates | Outcome / milestone |
| --- | --- | --- |
| Sprint 1 | 19–30 October 2026 | Verified baseline, launch-source list and live-source feasibility |
| Sprint 2 | 2–13 November 2026 | Reliable availability identity and partition reconciliation |
| Sprint 3 | 16–27 November 2026 | Multi-site beta with complete search experience |
| Sprint 4 | 30 November–11 December 2026 | Operational validation and conditional MVP release |
| Contingency | 14–18 December 2026 | Up to five working days for source/access or release blockers; no added features |

## Sprint 1 — prove the sources and baseline

Goal: establish what works and whether the proposed launch catalog is achievable.

| Work item | Estimate | Owner |
| --- | --- | --- |
| P01: Set up Postgres, migrations and seed; run existing tests, frontend lint/build; record failures and skips | 1.5 days | Engineer |
| P02: Confirm prioritised website URLs, single-day scope, inclusive day +14 horizon, hosting budget/domain and public booking model; remove synthetic courses from proposed production catalog | 1 day | Engineer + product owner |
| P03: Verify Mandalay responses and booking links, capture fixtures and document access/cadence constraints | 2 days | Engineer |
| P04: Spike a second website implementation and estimate remaining adapters | 2 days | Engineer |
| P05: Finalise slot identity, coverage model, migration and acceptance cases | 1.5 days | Engineer + QA |
| Integration, review and planning | 2 days | Team |

Exit: baseline test report available; source matrix has URLs, platform, feasibility and owner for every candidate; at least two implementations have evidence of feasible public access; correctness design agreed. If a source is infeasible, substitute it or reduce the launch count and revise dates explicitly. Live collection is not assumed proven by fixture tests.

## Sprint 2 — make availability trustworthy

Goal: publish correct bookable capacity and reconcile completed coverage safely.

| Work item | Estimate | Dependency |
| --- | --- | --- |
| P06: Migrate stable bookable-group identity; stop combining separate tee capacities | 2 days | P03, P05 |
| P07: Add execution/partition state and staging; transactionally reconcile full and verified-empty partitions | 3 days | P05, P06 |
| P08: Add bounded requests/retries, run locking and usable per-source outcomes | 1 day | P07 |
| P09: Test partial failures, empty sheets, invalid payloads, idempotence and capacity against Postgres | 2 days | P06–P08 |
| Integration, demo and planning | 2 days | Above |

Exit: a verified sold-out partition clears obsolete availability; failed/incomplete partitions preserve timestamps and data; independent groups never satisfy a larger party by aggregation; overlapping workers are prevented; integration checks pass with Postgres and without skips.

## Sprint 3 — deliver the multi-site beta

Scope update, 16 October 2026: the owner approved a Mandalay-only first beta, with Morack/Glen Waverley following afterward. P10's remaining integration work moves to the follow-up backlog. Initial public hosting and bounded collection are brought forward to support this beta. The original calendar below remains an estimate, not the actual implementation dates.

Goal: users can search verified sources and understand result coverage.

| Work item | Estimate | Dependency |
| --- | --- | --- |
| P10: Implement second source adapter and onboard a third real course; add regression fixtures | 3 days | P04, P07 |
| P11: Add enabled-course filtering, future-only and inclusive day +14 horizon validation (15 collected dates), bounded results, stable sorting and coverage metadata | 2 days | P06, P07 |
| P12: Add course selection, slot freshness, timezone/unit labels, partial-coverage states and request-race handling to web | 2 days | P11 |
| P13: Add API/browser acceptance checks and conduct mobile/keyboard review | 1 day | P10–P12 |
| Integration, beta demo and planning | 2 days | Above |

Exit: proposed three-course/two-implementation target reached or explicitly revised; complete user journey works in staging; no stub course leaks into catalog/search; no expired or already-started slots returned; API and frontend agree on the contract.

## Sprint 4 — validate and launch

Goal: demonstrate that the system stays useful and recoverable without manual supervision.

| Work item | Estimate | Dependency |
| --- | --- | --- |
| P14: Deploy public HTTPS frontend/API, private database and scheduled worker; configure DNS/TLS, readiness, logs, alerts and backups | 2 days | P08, P11 |
| P15: Verify source parity samples, run API load checks and review operational dashboards | 1.5 days | P10–P14 |
| P16: Run source-failure and database restore drills; prepare deployment/rollback/runbooks and reconcile README | 1.5 days | P14 |
| P17: Fix findings, finish acceptance review and prepare release candidate | 1 day | P13, P15, P16 |
| Integration, release review and deployment | 2 days | All release gates |
| Reserved release-defect capacity | 2 days | As needed |

Begin the 72-hour staging soak no later than 7 December, allowing it to run while reviews and documentation continue. The soak is elapsed time, not three additional engineer-days. Material collection changes restart the affected soak evidence. Release on 11 December only if all gates pass; otherwise use contingency and publish a revised date.

Exit: verify account-free public access from an external network on mobile and desktop, day +14 inclusion/day +15 rejection and provider-release messaging; meet coverage, freshness and latency targets in the project plan; inspect source/result samples; pass complete automated checks; demonstrate backup recovery and source degradation; product owner accepts scope; named operator can deploy and respond to failures.

## Critical path and tracking

Website confirmation → source feasibility → identity/coverage design → reconciliation → adapters/API → web acceptance → operational soak → release. Source discovery and deployment preparation can overlap with independent work, but do not publish availability before reconciliation is safe.

At each sprint start, split items into small tasks with owners and revised estimates. At each review, record accepted criteria, source success/coverage metrics, unresolved defects and schedule changes. A feature is done when implementation, relevant tests, source fixtures or API contracts, documentation and staging demonstration are complete. Production release additionally requires the operational gates.

If capacity tightens, defer maps, alerts, accounts, extra courses beyond the agreed minimum, and multi-day search. Preserve group-capacity correctness, safe empty reconciliation, freshness, source transparency and recovery checks. If a required source needs extensive browser automation or cannot be accessed, re-estimate that integration before committing the remaining dates.

After MVP, prioritise validated user demand: more course adapters first, then multi-day search/location filtering, then saved preferences and availability alerts. These are unestimated follow-on work and are outside this release window.

## Added requirements and estimate impact

Public hosting and access without a Golf Booker account are mandatory MVP release criteria. Tee-time discovery and provider booking handoff must support the date exactly two weeks ahead, using a collection window of today through day +14 inclusive (15 dates). This updates the former 14-date window; it does not add in-app reservation or payment. Provider booking/release restrictions remain visible to users.

Keep the proposed sprint dates provisionally: hosting was already budgeted in Sprint 4, and the horizon adjustment belongs in Sprints 2–3 with regression checks. Confirm hosting feasibility and revise estimates in Sprint 1; allow contingency if deployment or provider release-window handling exceeds these allocations.
