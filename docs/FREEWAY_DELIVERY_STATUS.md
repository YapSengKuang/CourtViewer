# Freeway F1/F2 delivery status

24 October 2026, Australia/Melbourne. Implementation and release verification in progress.

- Owner extended this task from F1 to F2 and confirmed an agreed method: public Quick18 pages once daily. Details are recorded in `operations/FREEWAY_ACCESS.md`.
- F1 importer and isolated snapshot UI implemented. Three timestamped browser captures (24, 25 and 26 October tee dates) contain 377 standard offers. Every imported offer was independently compared against its captured DOM for time, starting course, capacity, price and booking link; see `evidence/freeway-source-parity.json`.
- Dedicated local `teetimes_test` created. Full Python suite: 119 passed, zero skipped. Eleven frontend tests, lint, TypeScript/static export passed. Patched Next.js to 16.4.3 and transitive Zod; npm audit reports zero vulnerabilities. The patch also resolved the previous Turbopack build failure in the approved build environment.
- Snapshot mobile layout checked at 390 × 844; keyboard interaction, filter changes and missing-date messaging verified. Source HTML is never published and snapshots never enter normal search or freshness counts.
- F2 guarded daily runner, independent workflow/catalog, per-course cadence/release metadata and detailed availability status implemented. The 60-minute freshness contract remains unchanged. No precise release cutoff is inferred: on 24 October the public site displayed 2 November offers despite the advertised eight-day language.
- Hosted additive migration `0005_freeway_metadata` applied; function ACLs retained. Freeway seeded with public flag off; Mandalay stays enabled.

Pending: preview/live deployment checks, hosted daily collection and anonymous-source parity, independent disablement verification, final release identifiers and owner acceptance. A genuine empty/unreleased source response and exact release boundary have not been verified. Unknown layouts continue to fail closed. F2 must not be described as fully accepted while those evidence gaps remain.
