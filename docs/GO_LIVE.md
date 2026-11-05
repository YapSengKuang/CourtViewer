# Seven-course launch

The local app is the reference for the new calendar. The live architecture is:
Python scheduled worker → PostgreSQL → Supabase read RPCs → static Next.js on
Cloudflare Pages. Public searches never start collection.

## Step 1: publish collected observations

`scraper/courses.live.yaml` contains only the seven verified MiClub courses.
`python -m golf_scraper.hosted` collects today through day +14 by default, using
three parallel hosts and serial, robots-aware requests within each host. It
publishes through the existing transactional pipeline rather than importing
potentially stale JSON files. All expected date/fee partitions are durable before
source requests. Verified-empty partitions clear old offers; failed partitions
retain original rows and observation timestamps. Database-backed cooldowns and
the global advisory lock coordinate local/legacy/hosted workers. Courses must be
seeded first; public enablement remains separate from collection.

Run once with the existing private `DATABASE_URL` (never a frontend variable):

```sh
COURSES_YAML=scraper/courses.live.yaml python -m golfdb.seed
python -m golf_scraper.hosted --days 15
```

No blocked sources or Freeway are included. Freeway keeps its isolated daily
collector and database guard.

## Remaining launch steps

2. Hosted API parity: supported holes, date/fee coverage, timestamps and existing
   24-hour observation-window work must match the local preview.
3. Schedule the new worker every 15 minutes on the default GitHub branch. Keep
   the operator stop switch, global lock and independent daily Freeway schedule.
4. Begin a 72-hour observation period. Record run durations, requested versus
   verified scopes, source failures, freshness and public HTTP checks. This period
   cannot be marked complete when the schedule is merely enabled.
5. Deploy the static calendar as a preview for online testing, then promote it
   after acceptance. Keep the previous deployment available for rollback.

The website's Refresh button rereads stored results. It does not start scraping.
Scheduled check times are targets; observation timestamps show actual data age.
