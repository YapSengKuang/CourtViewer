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

## Local scrolling improvement — 5 November 2026

The calendar now windows tee-time buttons in both directions, keeping a buffered
area around the scroll viewport. Course labels, row heights, the complete scroll
range and result counts remain intact. All API pages are still loaded; scrolling
never requests golf-provider pages. Memoised course grouping and lane layouts
avoid repeating layout work while scrolling. Passive scroll listeners schedule
measurements once per animation frame, with quantised bounds to avoid a React
update for every pixel.

Focused/selected buttons stay mounted. Tab navigation restores the complete
button sequence before the browser chooses its next focus target; pointer and
wheel interaction resume windowed rendering. In the narrow local browser, the
657-offer mixed-hole search initially mounted 55 buttons. Scrolling revealed
later times and clubs, and a Northcote offer still opened the correct price,
capacity, timestamp and booking link. Keyboard navigation exposed all 657
buttons. This measures rendered-card reduction, not a guaranteed frame rate.

Vertical scrolling now belongs to the document: the calendar expands to its full
row height, with horizontal scrolling retained inside the timeline. Rendering
bounds follow the calendar's position in the browser viewport, and the time
header follows page scroll. Browser validation on the 657-offer search measured
a 2,850 px calendar with equal client/content heights (no nested vertical scroll),
page scroll at 2,705 px with calendar scrollTop still zero, and a time header at
the top of the viewport. Later clubs and their cards were visible without page
horizontal overflow.
