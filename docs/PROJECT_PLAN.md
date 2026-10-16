# Golf Booker — project plan

Planning baseline: 16 October 2026. Implementation and hosted verification are in progress. The static frontend is deployed at https://golf-booker-beta.pages.dev with a Supabase Free database in Sydney. Live collection is only partially verified; courses remain disabled publicly and the beta acceptance gate is still open. The foundation table below records the original planning baseline; current evidence is in [Sprint 3 status](SPRINT_3_STATUS.md).

## Product objective

Help golfers find available tee times across a maintained list of golf booking websites within a chosen date and time window. Show comparable prices, capacity and freshness, then send the user to the provider to complete their booking. “Courts” in the request is interpreted as golf courses and tee times.

The MVP supports a single date, a same-day time window, party size, 9/18/either holes, course selection, and time/price sorting. It searches stored availability from today through today + 14 days inclusive in each course’s timezone (15 calendar dates), so users can find and follow booking links for tee times exactly two weeks ahead. Provider release windows still determine whether those times are bookable. Multi-day searches are a later extension.

## Existing foundation

| Area | Evidence in project | Readiness and remaining work |
| --- | --- | --- |
| Catalog | `scraper/courses.yaml`, `db/src/golfdb/catalog.py` | Seven entries: Club Mandalay plus six synthetic courses. Only Mandalay has a real booking URL and platform parameters. Confirm the actual launch website list. |
| Storage | `db/src/golfdb/models.py`, Alembic migration | Courses, tee times and one current health record per course exist. Extend identity and scrape coverage before release. |
| Collection | `scraper/src/golf_scraper/spiders/` | MiClub adapter builds network requests; three other adapters use fixtures. No live reliability claim is made. |
| Reconciliation | `scraper/src/golf_scraper/pipelines.py` | Validates and upserts; preserves old rows on errors or zero items. Cannot yet distinguish valid sold-out results from failure. |
| Search | `api/src/tee_api/routes.py` | Local-date/time, holes, minimum capacity, freshness and sorting exist. Add future-only results, course filtering and bounded responses. |
| Web | `web/src/components/search-page.tsx` | Form, cards, sorting, loading, empty and error states exist. Add coverage information, course selection and production copy. |
| Operations | `scraper/src/golf_scraper/run_all.py`, cron example, Makefile | Sequential isolated spider processes and proposed 15-minute scheduling exist. Deployment, locking, monitoring and recovery remain. |
| Verification | `db/tests/`, `scraper/tests/`, `api/tests/` | Automated tests exist; several require Postgres and otherwise skip. No test run was performed for this planning exercise. |

The root README describes older phases and understates the current MiClub implementation. Use the source files above as the baseline until documentation is reconciled.

## Scope and acceptance criteria

| ID | MVP requirement | Acceptance criterion |
| --- | --- | --- |
| R1 | Maintained website list | Launch catalog contains only verified real courses; synthetic entries never appear in production. Proposed launch target: three courses across at least two distinct website implementations. |
| R2 | Scheduled collection | Every enabled source is scheduled approximately every 15 minutes, subject to permitted source limits; one source failure does not prevent others running. |
| R3 | Window search | Results fall within the inclusive requested local time bounds and selected local date, are in the future and within the collection horizon. Invalid or unsupported windows receive clear feedback. |
| R4 | Party and holes matching | Each result supports the requested party in one bookable group and matches 9/18/either holes. Separate starting tees cannot create a false match. |
| R5 | Comparable results | Show course, location, local date/time and timezone, holes, spots, currency, price per player per round, and slot freshness. Never compare currencies as if equivalent. |
| R6 | Booking handoff | Each result opens a validated provider booking link; final availability and pricing are confirmed there. |
| R7 | Honest coverage | Hide slots older than 60 minutes. Distinguish no matching availability from sources that are stale, unavailable or not yet checked. A verified empty sheet removes obsolete slots only in its covered scope. |
| R9 | Public hosted access | Deploy a production website at a public HTTPS URL, accessible to anyone without a Golf Booker account, VPN or local setup. Public search and provider booking links work on desktop and mobile from an external network. Hosting includes the API, scheduled scraper and persistent database. |
| R10 | Two-week booking horizon | Search and collect today through local today + 14 days inclusive. Test day +14 inclusion, day +15 rejection and local midnight rollover. If a provider has not released day +14, show that limitation rather than claiming it is sold out. Booking is completed on the provider website under its own rules. |
| R8 | Operational readiness | Staging passes integration and user-flow checks, a 72-hour collection soak, a source-failure drill and a database restore rehearsal before launch. |

Out of scope: taking payment, reserving or guaranteeing a tee time, provider account automation, member-only access, bypassing source access controls, user accounts, alerts, maps, multi-day searches and mobile apps.

## Delivery approach and ownership

Assume one full-time engineer, a product owner available for weekly decisions, and part-time QA/design review. The engineer owns adapters, API, UI and deployment; the product owner confirms courses, access constraints and acceptance; QA reviews data parity and user journeys. Sprints are two calendar weeks, with roughly eight implementation days and two days for integration/review each. Estimates are provisional because source integration is the largest unknown.

Prioritise correctness before adding courses: validate Mandalay, resolve reconciliation and slot identity, add a second implementation, then complete search and production operations. Keep the existing Scrapy → Postgres → FastAPI → Next.js architecture. See [design](DESIGN_DOCUMENT.md) and [sprints](TIMELINE_AND_SPRINTS.md).

## Risks and decisions

| Risk / uncertainty | Response | Owner / decision point |
| --- | --- | --- |
| Launch websites unspecified | Start from Mandalay; obtain URLs and priority order. A blocked site is replaced or removed from the launch scope. | Product owner, Sprint 1 |
| Source structure or access changes | Capture representative fixtures, use platform adapters and bounded retries, monitor failures, disable unhealthy sources. Review each source's access conditions before enabling it. | Engineer, each onboarding |
| Separate tees summed into one party capacity | Preserve bookable group identity; migrate storage and remove aggregate capacity logic. | Engineer, Sprint 2 |
| Valid empty response treated as failure | Track expected and completed coverage; reconcile complete partitions including empty ones. | Engineer, Sprint 2 |
| Availability changes between scrape and booking | Show slot freshness and provider handoff; enforce stale filtering. | Engineer, Sprints 3–4 |
| Scope exceeds one engineer | Defer extra sources and optional filters before reducing correctness or release checks; use contingency if needed. | Product owner, each review |
| Dates or prices interpreted incorrectly | Verify local timezone, public adult fee, currency and unit against source samples. | Engineer and QA, each onboarding |

## Release measurement

Proposed targets, to confirm in Sprint 1: at least three verified courses across two implementations; at least 95% scheduled source partitions complete successfully during the 72-hour soak; no served slot older than 60 minutes; at least 95% of enabled course coverage refreshed within 30 minutes; API p95 below 500 ms on 10,000 stored slots at 10 concurrent clients in staging. Measure source outcomes even when a spider process exits successfully.

Validate at least 20 representative source/result pairs per launch implementation across two dates, both hole options where supported, and empty/sold-out cases. Record every mismatch and resolve correctness failures before launch. Cached availability can change after collection, so parity is checked against captured source responses as well as timestamped live samples.

Product-owner inputs needed during Sprint 1: final website URLs and priorities, confirmation of public golf tee times, single-day MVP approval, staffing, hosting budget, and the proposed launch targets. Work can begin on repository verification and correctness design while these are resolved.

## Technology stack options — free hosting requirement

Requirement added: target **$0 ongoing hosting cost** for the initial public MVP, using provider subdomains and free tiers. A purchased domain is optional and outside that target. Public access does not mean unlimited free traffic or guaranteed uptime. Stay on free plans, disable paid overages where supported, and stop/degrade gracefully when quotas are reached. Any paid upgrade requires a separate decision. Provider limits below were checked on 16 October 2026 and must be rechecked before deployment.

**Decision: option 4 selected by the project owner.** The other options are retained for comparison. Existing code remains the current implementation; the planned production serving path is static React/Next.js → Supabase SQL RPCs, with Python/Scrapy running in GitHub Actions. Every option must preserve inclusive day +14 coverage, group-capacity correctness, safe reconciliation and honest freshness.

| Option | Stack and hosting | Pros | Cons / free-tier constraints | Migration from current project |
| --- | --- | --- | --- | --- |
| **1. Keep the current Python stack** | Next.js static export on Cloudflare Pages; FastAPI on Render Free; Postgres on Supabase Free; Scrapy scheduled with GitHub Actions standard Linux runners | Reuses almost all backend, parser and database work; strong Python scraping support; relational queries and existing tests remain useful | Render cold starts affect first searches; four services to operate; Supabase storage/egress limits and possible inactivity pause; free scheduled scraping is conditional on Actions budget/repository visibility | **Low:** configure static export and hosting, add workflow/secrets, production CORS and database pooling; retain API and schema |
| **2. Static site plus availability snapshots** | React/TypeScript (reuse the current Next.js UI as a static export) on Cloudflare Pages; Python/Scrapy in GitHub Actions; publish versioned JSON availability snapshots as static assets; browser performs filtering | Smallest hosted architecture; no public API cold start or hosted database; retains Python parsing; static search traffic does not consume function/database quotas | Replace the database-backed serving path; snapshot size grows with sources; public dataset downloads; scheduled publication can lag; browser filtering and per-partition retention require careful implementation | **Medium:** retain adapters but add a snapshot writer, partition reconciliation and client search; current API/Postgres become optional development tooling |
| **3. Cloudflare TypeScript stack** | React/Vite on Pages; TypeScript/Hono API on Workers; D1 database; Cron Triggers with small per-partition collection tasks | Integrated hosting/API/scheduler; no separate sleeping Python web server; public search and scheduled collection can fit free tiers for a small workload | Rewrite Python parsers/API and PostgreSQL-specific schema; Free Workers have a very small CPU allowance; HTML parsing needs profiling; D1 write quotas can be exhausted by frequent full-window updates; browser automation is outside this baseline | **High:** port adapters and tests, change persistence to SQLite-compatible D1, implement scheduled partition dispatch and quota measurement |
| **4. React plus Supabase managed API** | Next.js static export or React/Vite on Cloudflare Pages; Supabase Free Postgres with SQL search functions exposed through its Data API; existing Python/Scrapy in GitHub Actions | Keeps Postgres and Python scrapers; removes the separately hosted FastAPI service and its cold start; straightforward path to later authentication if needed | Move API validation, timezone logic and coverage responses into SQL functions; database access policies need careful testing; Supabase quotas/pausing remain; scheduled scraping still depends on Actions | **Medium:** replace FastAPI serving with bounded SQL RPCs, adapt frontend API client, retain Python persistence and migrations with Supabase configuration |

### Verified limits that affect the choice

- **Cloudflare Pages:** static asset requests are free and unlimited; dynamic Functions consume Workers quotas. This supports static exports, not an assumption that every Next.js server feature runs free. [Pages pricing](https://developers.cloudflare.com/pages/functions/pricing/).
- **Render Free:** web services sleep after 15 minutes without inbound traffic and take about a minute to wake. Free background workers/cron are unavailable; its free Postgres expires after 30 days, so it is not the persistent database proposed here. Render itself advises against using free instances for production. Option 1 is therefore a public MVP compromise. [Render free services](https://render.com/docs/free).
- **Supabase Free:** includes a 500 MB database and 5 GB egress; automatic backups are not included. Free projects may pause after low activity over seven days. Plan separate exports and restore verification, rather than assuming managed automated backups are free. [Pricing](https://supabase.com/pricing), [pausing](https://supabase.com/docs/guides/platform/free-project-pausing).
- **GitHub Actions:** standard hosted runners are free for public repositories; private GitHub Free repositories have 2,000 included minutes per month. A 15-minute schedule is 2,880 runs per 30 days: even one billed minute per run exceeds that private allowance; two minutes is about 5,760 minutes before CI. Public repository visibility is a separate owner decision, not implied by a publicly accessible website. Keep secrets out of the repository. [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
- **Actions scheduling:** runs can be delayed or dropped under load, and public-repository schedules disable after 60 days without repository activity. Use an off-hour offset, concurrency lock, stale-data handling and schedule monitoring. It supports a nominal 15-minute schedule, not a guaranteed freshness SLA. Do not make a private repository public automatically. [Scheduled workflow behaviour](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
- **Cloudflare Workers Free/D1:** Workers allows 100,000 requests/day, 10 ms CPU per HTTP or cron invocation, and 50 subrequests per invocation. Network wait does not consume CPU, but parsing does. D1 includes 5 million rows read/day, 100,000 rows written/day and 5 GB total storage. At 96 refreshes/day, rewriting 1,000 rows each run already uses 96,000 writes before deletes, health updates or index effects. Partition and write-budget profiling is a selection gate for option 3. [Workers limits](https://developers.cloudflare.com/workers/platform/limits/), [D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/).
- **Vercel Hobby:** a possible personal-project frontend host, but restricted to personal non-commercial use; Hobby cron is limited to once daily, so it cannot supply the proposed collection cadence. It is not the default host in these four options. [Hobby plan](https://vercel.com/docs/plans/hobby), [cron limits](https://vercel.com/docs/cron-jobs/usage-and-pricing).

### Selected stack and delivery impact

**Option 4 selected; validate its free-tier capacity before launch:** preserve the existing Python scrapers and Postgres model while avoiding a sleeping public API service. It offers a useful balance of existing-code reuse and a small free hosted footprint. This recommendation is conditional on an acceptable free Actions execution budget, sufficient Supabase capacity, and a successful SQL search/access-policy spike. Expose only bounded public read functions with narrowly granted privileges; keep collection writes and credentials restricted to the worker. Do not expose raw operational errors or unrestricted table access through the public client.

If the repository must stay private and measured Actions usage exceeds its free allowance, options 1, 2 and 4 do not satisfy the $0 / 15-minute combination as described. Evaluate option 3 against actual parser CPU and database writes. If it also fails, reduce source count or refresh frequency with an explicit scope change; do not claim the existing requirements fit free quotas. A 60-minute freshness cutoff still applies even when collection is delayed.

Option 1 is the fastest path if retaining FastAPI matters more than cold starts. Option 2 is the simplest hosted runtime for a small public catalog, at the cost of replacing the current serving design. Option 3 is worth a small feasibility spike if integrated free scheduling is the priority; a full rewrite should not precede that evidence.

Add a **two-working-day, provisional stack feasibility task in Sprint 1**, charged against existing source/design investigation capacity: deploy one real-source slice, measure scrape minutes/CPU, rows written, payload size and database egress, test anonymous access, and record quota headroom. Confirm repository visibility preference and free-account eligibility without changing them. Re-estimate remaining work after the result; option 1 is most likely to retain the existing dates, options 2/4 may use contingency, and option 3 requires a new estimate. These are planning judgments, not measured implementation estimates.

The design document and sprint plan must use option 4 as the production target. Retain FastAPI only as existing code/reference while migrating search to SQL RPCs; validate the backup method and API contract during the feasibility task. Treat performance/coverage targets as measured release goals rather than provider guarantees; cold starts or free-tier pauses may require an explicit target revision.


### Zero-spend controls for selected option 4

Policy: **stop work or restrict service before enabling paid usage**. Limits below are planned controls, not settings already applied to provider accounts. Billing settings are the charge-prevention boundary; application throttles help preserve availability but cannot guarantee protection against anonymous traffic or direct API abuse.

| Component | Billing protection | Proposed workload controls |
| --- | --- | --- |
| Supabase | Keep the project in a Free organization; no paid upgrade/add-ons. Supabase documents that Free-plan usage is not charged. Its Pro Spend Cap is not needed for Free and is not a universal cap if upgraded. | Alert at 70% of database/egress quota; at 80%, suspend nonessential writes and restrict public search if needed. Use 350 MB/4 GB as initial thresholds against the currently documented 500 MB/5 GB allowances. Retain only current/future availability plus 30 days of bounded execution summaries; prune old slots daily. |
| GitHub Actions | Where supported, set an Actions product budget of $0 with **Stop usage when budget limit is reached** enabled; confirm the account UI accepts/enforces it. Alerts alone do not block spending. An account without a valid payment method blocks usage beyond its included quota. Account-wide payment changes require a separate decision. | Standard Linux runners only; one scrape job at a time; 10-minute job timeout, bounded retries, no unbounded matrices, minimal caches and short artifact retention. For a private GitHub Free repository, reserve 500 of 2,000 minutes for CI and stop scheduled scraping at a planned 1,500-minute monthly allocation; measure all account usage because allowances are shared. This soft minute guard supplements provider blocking. |
| Cloudflare Pages | Use Free static hosting and its included subdomain. No paid Workers plan, paid add-ons or domain purchase. | Deploy UI only on code changes, not on each scrape. Avoid Functions initially. Fetch data only on explicit search, debounce repeat submissions, reuse identical results briefly and bound response sizes. |
| Public SQL API | No paid API gateway or rate-limit service introduced by default. | Enforce 15-date horizon, party 1–4, 100 results default/200 maximum, bounded pagination and query timeouts server-side. Narrow grants/RLS, indexed queries, no anonymous writes and a tested switch to revoke anonymous search RPC access during abuse/quota exhaustion. Browser throttling is convenience only and cannot constrain direct callers. |

At 80% of a quota, start with the controls above rather than silently upgrading. Quota checks can lag, so thresholds are safety margins, not billing guarantees. If quota monitoring cannot read current usage, retain conservative fixed workload bounds and provider-level blocking. A disabled scheduler cannot run its own monthly reset: include an operator resume procedure or a separate bounded check. Keep the public UI available with an honest service-limited message; hide slots after 60 minutes instead of showing stale availability as current.

A private repository's 1,500-minute scrape allocation cannot sustain a 15-minute schedule all month, even at one billed minute per run. Measure runtime and propose a lower cadence if required; obtain scope agreement before changing freshness goals. Do not change repository visibility without the owner's instruction.

Release gate: record Free plan status, Actions hard-budget scope and stop setting (or absence of a payment method), runner type, usage thresholds, RPC limits and service-disable/recovery steps. Test circuit breakers with low test thresholds without deliberately consuming quota or generating charges. Keep exports/backups bounded within storage allowances. No paid upgrade is automatic.

Sources: [Supabase cost controls](https://supabase.com/docs/guides/platform/cost-control), [GitHub hard budgets](https://docs.github.com/en/billing/how-tos/set-up-budgets), [Actions billing and quota blocking](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [Pages static pricing](https://developers.cloudflare.com/pages/functions/pricing/). Checked 16 October 2026.


### Sprint 1 owner decisions

The owner supplied the following additional source URLs for investigation: [Glen Waverley / Golf Booking](https://www.golf-booking.com/en/club/glen-waverley-golf-course) and [Morack / MiClub](https://morack.miclub.com.au/guests/bookings/ViewPublicCalendar.msp). Together with Mandalay these are the proposed three-course, two-platform launch set, conditional on source feasibility. Do not substitute synthetic courses for missing integration evidence.

The owner confirmed that a public repository is acceptable. This permits planning around free standard GitHub Actions runners for a public repository; actual repository visibility has not been changed. Billing controls, bounded jobs and usage monitoring still apply. See [Sprint 1 status](SPRINT_1_STATUS.md) for investigation results and remaining work.
