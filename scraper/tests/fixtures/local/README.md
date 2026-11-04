# Sanitised MiClub parser fixtures

Captured during source inspection on 4–5 November 2026 (Melbourne). Dates in the
tee sheets are 5–6 November (midweek) and 7 November (weekend), 2026.

Source URLs:

- Morack: `https://morack.miclub.com.au/guests/bookings/ViewPublicTimesheet.msp?bookingResourceId=3000000&selectedDate=2026-11-05&feeGroupId=1115048`
- Morack weekend: same parameters, `selectedDate=2026-11-07`.
- Yarra Bend 18 holes: `https://yarrabend.miclub.com.au/guests/bookings/ViewPublicTimesheet.msp?bookingResourceId=3000000&selectedDate=2026-11-05&feeGroupId=991`
- Yarra Bend 9 holes: same parameters, `feeGroupId=993`.
- Yarra Bend weekend: same 18-hole parameters, `selectedDate=2026-11-07`.
- Yarra Bend Friday: same 9-hole parameters, `selectedDate=2026-11-06`.

Fragments contain two standard adult offer rows (one per observed adult price
for the Friday fixture) and, where present, one row
offering only configured excluded fees. Cell contents are removed completely;
only the original available/taken states remain. These small fragments are
offline regression inputs, not full-sheet coverage or current availability.
