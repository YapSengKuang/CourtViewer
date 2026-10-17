# Hosted bootstrap

`bootstrap_supabase.sql` is a fresh-project baseline generated from the local Alembic `0004` schema and function definitions. It was applied to Golf Booker using Supabase's migration API. It intentionally refuses a database with existing application tables; use the regular Alembic chain for upgrades, not this bootstrap.

It contains no source observations, credentials or enabled courses. All application tables and Alembic metadata have RLS; only the four intended lookup RPCs receive anonymous execute grants. The coverage helper stays private.

Hosted operator settings applied separately:

```sql
ALTER ROLE anon SET statement_timeout = '3s';
ALTER ROLE anon SET lock_timeout = '1s';
NOTIFY pgrst, 'reload config';
```

The restricted scraper role is provisioned separately with a generated password. Never put its password or connection string here. Its allowed operations are SELECT and row locking on courses, collection CRUD on tee times/executions/partitions, SELECT/INSERT/UPDATE on scrape health, and usage on the three insert sequences. RLS policies apply only to that role. It has no course-flag, schema-management or role-management access. Use the session pooler, not transaction pooling.

See `docs/SPRINT_3_STATUS.md` for actual hosted checks and unresolved release gates.
