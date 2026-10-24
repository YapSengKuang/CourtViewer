# Freeway F1/F2 delivery status

24 October 2026, Australia/Melbourne. **F1 engineering delivery published. F2 daily search enabled with explicit acceptance gaps.** Owner review remains open; this is not a claim that all F2 gates or F3 reliability work are complete.

## Published result

- Live search: https://golf-booker-beta.pages.dev — select Freeway Golf Course.
- Isolated historical demo: https://golf-booker-beta.pages.dev/freeway-snapshot.
- Preview: https://freeway-preview.golf-booker-beta.pages.dev/freeway-snapshot.
- Production frontend deployment: `7f1c3a88` (artifact built from `6abbba9`; subsequent lockfile/test-only repair at `c736a14`). PR #2 merged as `df45df9b87060731c2a69f73a3c579abfbc95b11`.
- Hosted Alembic revision: `0005_freeway_metadata`. Existing bounded RPC signatures and grants preserved; Freeway and Mandalay enabled, Morack disabled.

## F1 verification

- Offline importer accepts explicit source URL, local date and actual timezone-aware capture time; validates date/group/rate/capacity/price; strips tracking and unrelated personal/script content; never connects to the availability database.
- Three timestamped browser captures for 24, 25 and 26 October contain 377 standard offers. Every imported offer was independently compared with captured DOM time, starting course, capacity, price and booking link. Evidence: `evidence/freeway-source-parity.json`.
- Snapshot view has date/time/players/holes filters, separate starting tees, pagination, explicit capture date/timezone and selected-date “Check current times” handoff. Unsupported dates say “No snapshot captured for this date”. Historical snapshots never enter normal results or freshness counts.
- Verified local mobile layout at 390 × 844, keyboard edits, missing-date and filter behavior; verified hosted snapshot date selection and pagination. Rebuilt with the feature flag false and verified the disabled view, then restored the true build. Live deployment remains enabled.
- Full Linux CI passed: 120 Python tests, zero skips; eleven frontend tests, lint, TypeScript and static export. Next.js 16.4.3 and transitive Zod fixes have zero npm audit findings. A Linux-only optional-dependency lockfile omission was repaired using CI's npm version and the clean install/build rerun successfully.
- CI: https://github.com/YapSengKuang/CourtViewer/actions/runs/40058442657.

## F2 hosted collection and search

The owner extended the task to F2 and confirmed the agreement is for public Quick18 pages **once daily**. The scoped exception and cadence are recorded in `operations/FREEWAY_ACCESS.md`. Collection uses a separate workflow/catalog and an independent stop switch; Mandalay retains its original schedule and public flag.

- Stop-switch test skipped the job: https://github.com/YapSengKuang/CourtViewer/actions/runs/40058701321.
- First collection: https://github.com/YapSengKuang/CourtViewer/actions/runs/40058917259. Provider execution ran 14:35:48–14:37:00 AEDT on 24 October. It accepted 1,306 offers across ten date partitions (24 October–2 November). Schema/price/capacity/provider-link checks found no invalid stored offers.
- Five dates (3–7 November) returned an unverified empty/unreleased layout. They failed closed, produced no offers and report `unavailable`; the execution is **partial** and the workflow correctly reports failure. It is not a fully successful collection run. Accepted dates remain usable.
- Re-dispatching the workflow passed without any new provider requests because today's durable attempt was already recorded: https://github.com/YapSengKuang/CourtViewer/actions/runs/40059314192. A failed attempt also consumes the day's allowance.
- Anonymous-role SQL verified two accepted dates and the unavailable state before public enablement, using a rolled-back flag change. After enablement, anonymous HTTPS checks returned 146 offers on 25 October and 117 on 26 October for two players, with complete date coverage. 3 November returned no rows and `unavailable`. Evidence: `evidence/freeway-hosted-http.json`.
- Public browser checks verified current-day nine-hole results, future-date results, separate starting tees, prices/capacity, Page 2 with Next disabled at the end, and booking handoff. The provider detail page confirmed 26 October at 15:16, Freeway, nine holes and $32/player. No booking, terms acceptance or payment was submitted.
- Supabase advisors retain the existing intentional anonymous SECURITY DEFINER RPC warnings and private migration-table policy notice. The coverage helper remains inaccessible to anonymous users; no direct table grants were added.

## Remaining acceptance and operating limits

- F2 is **not fully accepted**: a positively identified sold-out/unreleased response, exact release-boundary evidence, and owner acceptance remain open. On 24 October the site displayed 2 November offers despite the marketing text's eight-day wording, so no exact 7 pm/eight-day cutoff is inferred.
- Once-daily collection cannot provide continuously current availability. The existing 60-minute freshness limit remains unchanged: current normal-search offers disappear after that age, and the UI explains daily collection and directs users to Freeway. The snapshot demo remains explicitly historical.
- The scheduled cycle is 10:17 UTC (21:17 AEDT / 20:17 AEST), subject to GitHub delays. Today's scheduled invocation will skip because the manual acceptance run already consumed today's cycle.
- Mandalay remains enabled and its existing collection workflow's latest inspected run succeeded. Scheduler timeliness is not an uptime guarantee; no new reliability claim is made.
- Configuration/RPC backup and rollback steps: `operations/FREEWAY_RELEASE.md`. Full database restore rehearsal, billing/usage evidence and the 72-hour soak remain F3 work.
