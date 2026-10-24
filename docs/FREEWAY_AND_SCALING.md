# Freeway integration and scaling beyond ten courses

Original assessment, 24 October 2026. **Superseded for delivery/access status by [Freeway delivery status](FREEWAY_DELIVERY_STATUS.md): the demo is live and agreed daily search is enabled with acceptance gaps.** Freeway is a must-have next integration, ahead of the previously proposed Morack/Glen Waverley expansion.

The [Freeway sprint plan](FREEWAY_SPRINTS.md) is the current delivery backlog: first a clearly labelled hosted snapshot proof of concept, then refreshed availability conditional on source access, followed by reliability and scaling measurements. The remaining steps below describe the refreshed-availability milestone; isolated snapshot demonstrations do not require enabling the live collector.

## Freeway: implemented versus blocked

The public [Quick18 matrix](https://freeway.quick18.com/teetimes/searchmatrix) was retrieved once on 24 October. Its own date links use `?teedate=YYYYMMDD`. The page has standard 9/18-hole rates, concession columns, individual group capacities and two provider course identities: `1598` (Freeway) and `1599` (Back 9). A captured page contained 65 groups and 105 standard offers before filtering elapsed tee times. Those are capture-time observations, not current availability.

The page states bookings open at 7 pm daily, eight days ahead. Do not assume the project's day +14 window means Freeway has released that date. The precise release boundary, unreleased-day layout and verified sold-out layout still need acceptance evidence. The page also states a payment processing surcharge; captured prices are the displayed standard round rate, not a guaranteed final checkout total.

The [robots policy](https://freeway.quick18.com/robots.txt), retrieved on the same date, explicitly excludes Scrapy, curl and OpenAI clients, among others. Recurring collection is therefore disabled. The next external dependency is a permitted availability feed or an agreed collection method with Freeway/Quick18. This is not a claim that ordinary browsing requires permission. No alternate identity, login, CAPTCHA workaround or booking action was used after discovering the policy.

Implemented locally:

- A **date-specific direct link** in the search page, explicitly stating that Freeway is not included in aggregated results yet. It uses the form's date and opens the provider website; users choose holes/players there. No tracking token is retained.
- A reusable **Quick18 candidate adapter**, configured by provider course IDs and exact standard rate labels/IDs. Separate starting tees and rates retain separate identities; concession and twilight rates are excluded.
- Strict validation of response date, unfiltered search controls, group capacity, prices, course identity and same-host booking links. Changed, empty and unreleased layouts fail closed, preserving cached data rather than asserting sold-out coverage.
- A minimal, sanitised two-row fixture from the captured page and regression tests. No advertising scripts, attribution tokens or personal booking details are retained.
- `scraper/courses.freeway.yaml` is a separate candidate catalog with collection disabled. It is not included in `courses.mandalay.yaml` or the scheduled workflow. Production preflight continues to reject it; a candidate parser is not a verified production integration. The spider also explicitly evaluates the Scrapy robots policy.

Remaining before Freeway can appear in aggregated results:

1. Establish the permitted feed/collection method and record it. An approved feed may need a different transport; do not simply disable robots handling.
2. Capture representative weekday/weekend dates, 9/18-hole offers, both starting courses, empty/sold-out and unreleased states through that method. Verify at least 20 source/result pairs across two dates. Confirm capacity is one bookable group and final-price wording is clear.
3. Model provider release metadata in the catalog/database/public course response and UI: distinguish **not released**, **verified empty**, **failed** and **stale**. Until then, unknown layouts must remain incomplete, never empty. The candidate currently uses the common 15-date horizon and is deliberately not ready for live scheduling.
4. Run database-backed reconciliation/search tests, update preflight only after acceptance, add Freeway to the launch catalog, seed it without enabling its public flag, collect successfully and verify the public date query before enabling it.
5. Deploy the reviewed frontend/collector changes and run the operational soak. This change has not been deployed and does not alter hosted account settings.

## Architecture for ten-plus courses

Keep the static frontend, database read API and Python collectors. Course count alone is not a reason to rewrite them. Scale collection independently of user search: selecting a date should query saved data, not contact ten providers during a page request.

### 1. Reuse adapters; configure courses

Maintain one adapter per platform (MiClub, Quick18, etc.). Course configuration supplies the host, provider IDs, timezone, accepted rate mapping, access status and release rules. A new course using an existing platform should usually require configuration plus source-specific fixtures, not copied scraper code. Quick18's new candidate follows this pattern, but its generic structure is not evidence that every Quick18 site is compatible.

### 2. Schedule small units of work in bounded batches

Use `(course, local date, rate group where needed)` as the logical work unit. Batch multiple dates into a worker to avoid one GitHub job/install per date. Start with a small measured number of concurrent course batches; retain one request at a time per provider origin and coordinate that limit across workers sharing the same host. Use per-course leases/locks, attempt deadlines and backoff so one slow course cannot exhaust every other course's time budget.

The current runner is sequential by platform with a global advisory lock and a 300-second spider limit. Merely adding workflow parallelism would collide with that lock. Course selection, narrower locks and bounded dispatch need to be implemented together, while preserving publication's newer-snapshot checks. Introduce a durable queue only when retry/backlog behaviour warrants it; a new service is not required just to reach ten courses. Scrapy provides the underlying [domain concurrency, delays and robots controls](https://docs.scrapy.org/en/latest/topics/settings.html).

### 3. Avoid waste without weakening freshness

One matrix response can contain both 9/18-hole offers: Quick18 needs one request per date, not one per player count or hole option. Do not repeatedly request unreleased dates once release rules are verified. Keep released-date refresh within the existing freshness goals; if changing cadence for distant dates, revise the displayed freshness/coverage contract explicitly. Cache/deduplicate browser requests separately from collection. Never reuse an expired result as fresh.

### 4. Reduce database latency and measure storage

Batch initial partition registration and immutable metadata reads, retaining atomic publication per partition. Benchmark before replacing inserts or adding indexes. If history lookup becomes expensive, keep a compact latest-coverage record per course/date alongside bounded diagnostic history. Inspect representative plans with [EXPLAIN ANALYZE](https://www.postgresql.org/docs/current/using-explain.html) on a disposable database.

Planning example, not measured demand: ten courses × 15 dates × two requests/date = 300 requests/cycle and 28,800 requests/day at 15-minute intervals. If each request produces a history partition, 30-day retention approaches 864,000 records before other tables/indexes. Quick18 can halve the request count for its combined rate matrix. Actual request counts, storage, write cost and egress must be measured; free-tier fit is not guaranteed.

### 5. Measure every course, not just job exit status

Track last complete date coverage, request/parse/publication durations, error rate, oldest pending work, rows written, database growth and public query latency. Alert when an enabled course misses its freshness target. Keep independent source failures visible and preserve stale-data exclusion. Finish backup/restore and failure drills before scaling the public catalog.

## Prioritised delivery plan

| Priority | Work | Completion condition |
| --- | --- | --- |
| P0 | Freeway access/feed and source acceptance | Approved method, date/release/empty fixtures and parity evidence |
| P0 | Freeway publication and UI integration | Stored date searches match source; release states honest; successful hosted run |
| P1 | Batch database registration and lock dependencies | Fewer measured round trips; all reconciliation/overlap tests pass |
| P1 | Course/date dispatch in bounded batches | A failed course cannot starve others; no overlapping writes or per-host rate violations |
| P1 | Reproducible installs, monitoring and bounded history | Predictable dependencies, observed freshness and storage headroom |
| P2 | Ten-course staging benchmark and soak | All courses refreshed within agreed targets; search p95 <500 ms at 10 concurrent clients; 72-hour soak and restore drill |

Freeway remains a required deliverable, not a deferred optional course. The access dependency is unresolved, so a completion date for live availability cannot yet be promised. The date-link fallback is useful immediately but does not satisfy the requirement to aggregate Freeway times.

## Validation of this change

- Python suite: **58 passed, 51 skipped**. Database tests could not reach local `teetimes_test`, including after an escalated retry; no database integration pass is claimed.
- Frontend: **8 tests passed**, ESLint passed, and `tsc --noEmit` passed.
- Production build: blocked by a Turbopack worker-port `Operation not permitted` error, including after an escalated retry. Static export and browser acceptance remain outstanding. The build also emitted a dependency security advisory; that advisory was not independently verified or addressed in this change.
- Parsed the full already-retrieved matrix offline; subsequent automated source requests were not made. The checked-in regression fixture contains only form controls, headings and two anonymous availability rows.
- `git diff --check` passed. No deployment, public-course enablement or live collection was performed.
