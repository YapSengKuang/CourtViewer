# Collection publication and recovery

## Deploying the identity migration

Pause collection and take a database backup before migration. Deploy the scraper, API and frontend together with `alembic -c db/alembic.ini upgrade head`. Old scraper code references the removed uniqueness constraint and must not run after migration. New scraper code requires the new schema.

Revision `0003_partition_identity` preserves cached tee times and expands uniqueness to `(course_id, starts_at, holes, source_partition, source_slot_key)`. It expires existing MiClub observations because those may contain combined starting-tee capacities. They become invisible to the 60-minute freshness filter until replaced by correct observations. Old `window`-scope MiClub cache is not reused as a date/fee-group snapshot. Prune expired/past cache as a separate retention task.

Migration downgrade refuses when multiple groups share one legacy time/holes key; it never silently merges capacities. If rollback is required, archive/rebuild derived cache under a documented maintenance procedure before downgrading. No production migration or course enablement is performed by the implementation tests.

## Running collection

Use `python -m golf_scraper.run_all` with a direct/session Postgres connection. Transaction-pooling endpoints do not preserve session advisory locks. Exit 0 means all discovered spiders have successful durable execution outcomes, exit 1 means failure/partial/missing/interrupted execution, and exit 2 means another CLI worker owns the lock. Retain request throttling and provider access policies; this does not activate a schedule.

Each spider must register all expected partitions and their aware time bounds before requesting data. Each response must positively establish completeness before marking its partition complete. Missing selectors, unknown booking-cell states, mismatched dates, unexpected item scope and invalid observations fail closed. Do not infer completeness from item counts. Synthetic adapters are test fixtures, not launch sources.

Data is staged in memory, capped at 20,000 unique observations per spider. The pipeline publishes at `spider_closed`, after all items are processed and the real close reason is known. A verified complete partition replaces only its own scope inside one database transaction. A valid empty response removes its old rows; any failed replacement rolls back. Other partitions can publish independently, with the course/execution marked partial. Course success timestamps advance only for a fully checked course. Retained rows never receive a new observation timestamp from a failed response.

## Inspection and recovery

Inspect private `scrape_executions` and `scrape_partitions`: execution ID, course, key, bounds, status, staged accepted/rejected counts and internal error. These tables have RLS and no public grants. User health remains sanitised; raw errors are for operators. `accepted_count` counts staged unique observations, not necessarily published observations on failed/superseded partitions.

- Retry transient failures normally; a new successful snapshot reconciles its scope safely.
- Fix parser/configuration failures against fixtures before retrying.
- Review overdue `running` executions after the nine-minute run budget: the parent itself may have been interrupted. Confirm no worker is active before marking an abandoned execution interrupted or restarting. Never remove a live database lock manually as a shortcut.
- On lock-connection loss, stop the affected worker and inspect coverage. Course locks and snapshot ordering prevent an older completed snapshot replacing a newer one, but do not substitute for healthy scheduler lock connectivity.
- Keep old observations hidden after 60 minutes and disclose partial/unknown coverage. Bookings remain on the source website.

Before production, schedule bounded retention using the existing worker infrastructure: retain completed execution history for 30 days and cascade-delete its partition rows; prune past availability separately. Do not delete pending/recent execution records or add paid storage to avoid retention. Monitor database size and egress with the project plan's quota thresholds. Retention scheduling, hosted-role checks and actual account billing controls remain deployment tasks.
