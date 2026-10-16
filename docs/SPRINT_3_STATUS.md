# Sprint 3 — beta search and source integration

In progress on `codex/sprint-3`. This batch does not deploy a beta or complete the three-course/two-platform target.

## Implemented

- Migration `0004_beta_search` adds `golf_search_v2` and `golf_courses`. Enabled-course filtering, local today through +14, capacity/freshness constraints and group identity remain intact. Currency/price ordering occurs before paging; results use 100-row pages in the client, at most 200 server-side, with bounded offset and `has_more`. Existing v1 remains available for older clients.
- Date coverage reports each enabled/selected course as complete, incomplete, unchecked or outside horizon. It derives status from the latest record per expected source partition overlapping the selected date, with a 60-minute freshness threshold. Failed/pending partitions do not count as checked. It is observed source coverage, not a promise that a provider has released every future date or that a booking remains available.
- The helper coverage function is private; only the bounded v2 search and enabled-course catalog RPC are granted anonymously. Public/default grants are revoked explicitly, including Supabase anonymous/authenticated default grants. No public course was enabled.
- The frontend has course selection, server-side sort selection, page controls, per-course incomplete-coverage messaging, local timezone labels and course date bounds. Page navigation preserves the submitted filters; editing the form requires Search to apply. Price sort groups currencies rather than comparing them as equivalent. Concurrent database refreshes can shift offset pages; paging is not a frozen snapshot.
- The local development FastAPI route now supports course filters/paging, currency-aware price order, future-only slots and horizon checks. It retains the development catalog including fixtures; production RPCs remain opt-in only. Development API responses do not claim partition coverage.
- `COURSES_YAML` now resolves consistently from the repository root for both seeding and spiders. The runner selects configured adapters and fails on missing adapters rather than silently skipping a platform. The separate candidate catalog `scraper/courses.beta.yaml` contains Mandalay and Morack; it does not toggle database public flags.

## Source findings — 16 October 2026

Morack public calendar: resource `3000000`, nine-hole fee group `1115048`; fee group `197` is eight holes and excluded. The captured calendar has `publicCaptchaEnabled = false`; its public redirect requires no CAPTCHA token in that state. A public nine-hole sheet for 30 October was readable and contained standard `9 Holes Midweek` pricing. The parser now supports its date representation and explicitly configured fee labels, excluding junior/concession prices. A transformed two-row fixture stores only times, provider row IDs, fees and anonymous availability states, with personal data and unrelated scripts omitted. Other fee labels fail closed; full weekend/closed-date parity is not yet established. The captured robots policy allows ordinary user agents on guest booking paths while restricting specific bot agents and other paths; keep robots handling enabled and recheck conditions at deployment.

Glen Waverley's public page exposes a booking search script, but neither direct HTML inspection nor the browser showed working date/player controls or a verified availability response. No endpoint parameters were guessed and no adapter is claimed implemented. It remains the second-platform blocker. No CAPTCHA was solved and no reservation, account or payment action was taken.

References: [Morack calendar](https://morack.miclub.com.au/guests/bookings/ViewPublicCalendar.msp), [Morack robots](https://morack.miclub.com.au/robots.txt), [Glen Waverley](https://www.golf-booking.com/en/club/glen-waverley-golf-course).

## Validation and remaining gates

The static export builds successfully locally. Six frontend contract tests, lint and TypeScript pass. Browser checks against the exported page verified the controls, service-unavailable message, backwards-window validation and mobile layout at 390 × 844; the temporary viewport was reset. Actual hosted search, returned cards/pagination interactions with real data, keyboard journeys and booking handoff still require integrated staging verification.

Python regression checks cover course selection, sorting before paging, page continuation, disabled-course rejection, horizon metadata, private grants, fresh-empty versus partial coverage, Morack fixture pricing and catalog adapter selection. Final counts are recorded in the commit summary.

Remaining before beta: complete Glen Waverley or explicitly revise the source target; verify full live source/date/fee parity; configure Supabase/Pages Free accounts and database/API roles; verify hard billing controls; measure collection runtime and quota headroom; deploy staging and run end-to-end acceptance. Do not describe Sprint 3 or the public beta as complete yet.
