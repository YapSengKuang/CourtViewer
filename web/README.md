# Tee time search

Next.js page for the search API. From the repo root, with the API already running:

```bash
cd web && npm run dev
```

Open http://localhost:3000. The page calls `http://localhost:8000` unless `NEXT_PUBLIC_API_URL` is set.
# Public hosting target

This project targets Cloudflare Pages Free as a static export. Run `npm ci`, `npm run lint`, and `npm run build`; publish `out/` from the `web/` directory. Use the included Pages subdomain. No Node.js server or Pages Functions are required for the frontend.

The client currently still uses the existing FastAPI contract via `NEXT_PUBLIC_API_URL`. The selected Supabase SQL API migration is pending; do not publish the app expecting that integration to work yet. Never put database credentials or a Supabase service-role key in a `NEXT_PUBLIC_*` variable. Production build verification and provider billing settings are release gates documented in `docs/SPRINT_1_STATUS.md` at the repository root.
