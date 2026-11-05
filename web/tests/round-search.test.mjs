import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/round-search.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { roundDates, resultsUrl, layoutSlots, timelineBounds, currentTimelineStart, calendarRenderWindow, calendarPositionVisible, hourLabel, slotMinutes, SLOT_WIDTH } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);

test('date choices include today through day +14 across daylight saving and year boundaries', () => {
  const previous = process.env.TZ;
  process.env.TZ = 'Australia/Melbourne';
  try {
    const days = roundDates(new Date('2026-10-03T12:00:00+10:00'));
    assert.equal(days.length, 15);
    assert.equal(days[0].value, '2026-10-03');
    assert.equal(days.at(-1).value, '2026-10-17');
    assert.equal(new Set(days.map(d => d.value)).size, 15);
    assert.match(days[0].label, /^Today/);
    assert.match(days[1].label, /^Tomorrow/);
    const year = roundDates(new Date('2026-12-25T12:00:00+11:00'));
    assert.equal(year.at(-1).value, '2027-01-08');
    assert.equal(roundDates(new Date('2026-11-04T14:00:00Z'))[0].value, '2026-11-05');
  } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
});

const slot = (id, clock, holes = 18) => ({ source_slot_key: id, source_partition: `${holes}`,
  starts_at_local: `2026-11-06T${clock}:00+11:00`, holes });

test('calendar stacks close and simultaneous groups without merging or overlapping them', () => {
  const slots = [slot('a', '07:00'), slot('b', '07:08'), slot('c', '07:00', 9), slot('d', '07:45')];
  const layout = layoutSlots(slots, 360);
  assert.equal(layout.positions.length, 4);
  assert.equal(layout.positions.find(p => p.slot.source_slot_key === 'a').left, 180);
  for (const first of layout.positions) {
    for (const second of layout.positions) {
      if (first === second || first.lane !== second.lane) continue;
      assert.ok(first.left + SLOT_WIDTH <= second.left || second.left + SLOT_WIDTH <= first.left);
    }
    assert.ok(first.lane * 52 + 16 + 44 <= layout.height);
  }
  assert.equal(slots[0].source_slot_key, 'a'); // Does not mutate the input.
});

test('timeline includes early and late rounds, uses course-local clocks and handles empty dates', () => {
  assert.deepEqual(timelineBounds([]), { start: 360, end: 1200 });
  assert.equal(slotMinutes(slot('early', '05:30')), 330);
  assert.deepEqual(timelineBounds([slot('early', '05:30'), slot('late', '23:50')]), { start: 300, end: 1440 });
  assert.ok(Number.isNaN(slotMinutes(slot('bad', '99:99'))));
  assert.equal(layoutSlots([slot('bad', '99:99')], 360).positions.length, 0);
});

test('results navigation keeps the selected date, party size and holes in the URL', () => {
  assert.equal(resultsUrl('2026-11-06', 4, '9'), '/results?date=2026-11-06&players=4&holes=9');
});

test('only today starts at the current course-local minute, including UTC date boundaries', () => {
  const now = new Date('2026-11-05T21:37:20Z'); // 8:37am on 6 November in Melbourne.
  const today = currentTimelineStart('2026-11-06', now, 'Australia/Melbourne');
  assert.equal(today, 517);
  assert.deepEqual(timelineBounds([], today), { start: 517, end: 1200 });
  const tomorrow = currentTimelineStart('2026-11-07', now, 'Australia/Melbourne');
  assert.equal(tomorrow, undefined);
  assert.deepEqual(timelineBounds([], tomorrow), { start: 360, end: 1200 });
  assert.equal(currentTimelineStart('2026-11-05', now, 'Australia/Melbourne'), undefined);
  assert.equal(hourLabel(today), '8:37am');
  assert.equal(hourLabel(480), '8am');
});

test('today retains a positive timeline after normal closing hours and just before midnight', () => {
  assert.deepEqual(timelineBounds([], 21 * 60 + 15), { start: 1275, end: 1320 });
  assert.deepEqual(timelineBounds([], 1439), { start: 1439, end: 1440 });
  assert.equal(hourLabel(1439), '11:59pm');
  assert.equal(hourLabel(1440), '12am');
});

test('calendar window keeps partially visible cards and reveals later times and courses', () => {
  const window = { left: 500, right: 1000, top: 300, bottom: 600 };
  assert.equal(calendarPositionVisible({ left: 450, lane: 0 }, 300, window), true);
  assert.equal(calendarPositionVisible({ left: 417, lane: 0 }, 300, window), false);
  assert.equal(calendarPositionVisible({ left: 600, lane: 0 }, 240, window), true);
  assert.equal(calendarPositionVisible({ left: 600, lane: 0 }, 1000, window), false);
  const later = calendarRenderWindow(1600, 1200, 500, 500, 130);
  assert.equal(calendarPositionVisible({ left: 1700, lane: 0 }, 1300, later), true);
  assert.equal(calendarPositionVisible({ left: 0, lane: 0 }, 48, later), false);
});

test('render window buffers the viewport and quantises small scroll movements', () => {
  const a = calendarRenderWindow(600, 600, 400, 500, 130);
  const b = calendarRenderWindow(601, 601, 400, 500, 130);
  assert.deepEqual(a, b);
  assert.ok(a.left < 600 && a.right > 870 && a.top < 600 && a.bottom > 1100);
});

test('dense schedules keep all layout geometry while mounting only nearby cards', () => {
  const positions = Array.from({ length: 1000 }, (_, index) => ({ left: (index % 100) * 30, lane: Math.floor(index / 100) }));
  const window = calendarRenderWindow(1000, 0, 400, 200, 130);
  const visible = positions.filter(p => calendarPositionVisible(p, 48, window));
  assert.ok(visible.length > 0 && visible.length < 400);
  assert.equal(positions.length, 1000);
});

test('page scrolling reveals later rows using calendar position relative to the viewport', () => {
  const before = calendarRenderWindow(0, -600, 400, 800, 130);
  const after = calendarRenderWindow(0, 1200, 400, 800, 130);
  const card = { left: 0, lane: 0 };
  assert.equal(calendarPositionVisible(card, 48, before), true);
  assert.equal(calendarPositionVisible(card, 1500, before), false);
  assert.equal(calendarPositionVisible(card, 48, after), false);
  assert.equal(calendarPositionVisible(card, 1500, after), true);
});
