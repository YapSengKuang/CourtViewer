# Round planner and tee-time calendar

The local frontend uses a two-page flow:

1. `/` asks for date, players and holes using dropdown menus. There are 15 local
   calendar dates: today through day +14 inclusive; players are 1–4; holes are
   9, 18 or either. Defaults are today, two players and 18 holes.
2. `/results?date=YYYY-MM-DD&players=2&holes=18` displays a horizontal date strip
   and a course-by-time calendar. Search choices remain in the URL and survive
   reloads and browser back/forward navigation. Changing dates, players or holes
   searches the saved availability again.

The horizontal axis uses actual course-local tee times. Each vertical row is a
course. The time header and course labels stay visible while the calendar
scrolls. Nearby and simultaneous offers occupy separate lanes, retaining their
provider identities; group capacities are never added together. Each button
shows its start time and price per player, with different colours for 9 and
18 holes. Accessible button labels also include course, holes and capacity.

Selecting a button opens a nonmodal details panel with the course, round,
capacity, price, observation timestamp and provider booking link. Escape or the
close button dismisses it and restores focus to the selected time. Nothing is
booked or reserved by selecting a calendar button.

The timeline loads every bounded API result page before showing the calendar;
it does not silently omit courses after the first 100 offers. Superseded searches
stop requesting additional pages and cannot replace a newer selection. A failed
request hides the previous results and offers a retry.

The full date range is independent of the collector's sample horizon. A date
not collected is shown as “Not checked for this date”, never sold out. Verified
empty dates, incomplete coverage, stale observations and no matches for the
selected party size have separate messages. The local collector still defaults
to three days; this UI change does not add source requests or deploy anything.

The planner and calendar share the native stylesheet `web/public/round.css`,
loaded by the app layout. It does not need the Tailwind worker to serve the new
styles. Existing Tailwind-based pages retain their global stylesheet.

## Validation

- Frontend unit tests: 21 passed, including local-date arithmetic across DST/year
  boundaries, inclusive day +14, lane overlap, simultaneous provider groups,
  course-local positioning, all-page collection and superseded requests.
- Frontend lint and TypeScript checks passed.
- Production static export passed using `npx next build --webpack`, including
  `/`, `/results` and the existing snapshot page. The default Turbopack build
  still hits the existing CSS compiler worker's port-permission error, including
  after an escalated retry.
- Browser check: the starting-page dropdowns navigated to a 6 November 2026
  search for two players and 18 holes. The calendar displayed all seven course
  rows and 276 matching offers, with the full 15-date strip. A selected Bundoora
  slot displayed 6:00 am, A$40, four spaces and its provider booking link.
  A four-player, nine-hole search returned 345 offers. Selecting day +14 showed
  no offers and labelled every course as not checked, without implying sold out.

Run the local preview with `npm run dev:local` from `web/`. It reads the existing
collector output via the local API; the scraper itself is started separately.
