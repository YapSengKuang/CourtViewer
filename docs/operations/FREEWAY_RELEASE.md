# Freeway release and rollback

## Snapshot import

Save the public page HTML with its actual capture timestamp. Import offline:

```sh
.venv/bin/python -m golf_scraper.snapshots /path/to/saved.html \
  --source-url 'https://freeway.quick18.com/teetimes/searchmatrix?teedate=20261025' \
  --date 2026-10-25 --captured-at '2026-10-24T09:10:42+11:00' \
  --output web/src/data/freeway-snapshots.json
```

The timestamp above is an example: supply the real capture time. The importer rejects timezone-free/future timestamps, incorrect source/date, malformed rows and unknown empty layouts. It emits only allowlisted availability fields, strips link tracking parameters, and never writes availability tables. An older capture cannot replace a newer capture for the same date. Raw HTML stays outside the repository; public JSON contains no scripts, tracking or personal content.

Build with `NEXT_PUBLIC_FREEWAY_SNAPSHOT_ENABLED=true`. The isolated `/freeway-snapshot` view includes historical captures, explicit capture time/timezone, date/time/players/holes filters, pagination and a selected-date provider link. Unsupported dates say “No snapshot captured for this date”. Disable the flag and rebuild/redeploy to remove the view and navigation. The normal search never imports this bundle.

## Daily availability

See [owner-confirmed access scope](FREEWAY_ACCESS.md). Apply Alembic `0005_freeway_metadata` before running the new seed/collector. The additive migration preserves existing RPC signatures, grants and freshness rules. The hosted course starts disabled. Seed only `scraper/courses.freeway-live.yaml`, then run `python -m golf_scraper.daily_freeway` using the existing restricted collector credentials.

The `Collect Freeway daily` workflow uses the same repository secret as Mandalay and a separate `FREEWAY_COLLECTION_ENABLED` stop switch. Its one daily cycle is at 10:17 UTC (21:17 AEDT / 20:17 AEST); GitHub scheduling is best effort. A durable database attempt marker prevents another cycle on the same Melbourne date even after failure. It shares the existing global collection lock/concurrency group with Mandalay. Direct spider invocation cannot use the agreement exception. Do not manually erase an attempt marker to retry.

Inspect accepted partitions and anonymous date searches before enabling `freeway`. Invalid/ambiguous dates retain prior rows and report unavailable. The new `availability_status` distinguishes available, empty, unavailable, stale, unchecked and outside-horizon while retaining the old `status` for existing clients. There is no verified release rule, so no precise “not released yet” claim. All normal slots still expire after 60 minutes; daily collection does not provide all-day current coverage.

## Rollback

1. Set `FREEWAY_COLLECTION_ENABLED=false`; Mandalay's `GOLF_COLLECTION_ENABLED` remains unchanged.
2. Set `public.courses.public_enabled=false` only where `slug='freeway'`.
3. For snapshot rollback, rebuild with `NEXT_PUBLIC_FREEWAY_SNAPSHOT_ENABLED=false` and deploy, or restore the previous Cloudflare Pages deployment.
4. Keep the additive schema in place; older frontend/collector versions remain compatible. Do not downgrade columns while a collector is active.

The pre-migration course configuration, Alembic version and changed RPC definitions/ACLs were exported to `/private/tmp/freeway-release/pre-migration-backup.json`. This is a configuration/schema backup for this additive change, not a full database disaster-recovery backup or a completed restore drill. No availability rows were removed by the migration.
