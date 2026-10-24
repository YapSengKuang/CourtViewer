import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/snapshots.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { filterSnapshot } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
const data = JSON.parse(await readFile(new URL('../src/data/freeway-snapshots.json', import.meta.url), 'utf8'));

test('snapshot filters preserve date isolation, group capacity, holes and inclusive local time', () => {
  for (const snapshot of data) {
    for (const players of [1, 2, 3, 4]) {
      for (const holes of ['any', '9', '18']) {
        const matches = filterSnapshot(snapshot, '07:00', '15:00', players, holes);
        assert.ok(matches.every(o => o.local_time >= '07:00' && o.local_time <= '15:00' && o.spots_available >= players && (holes === 'any' || o.holes === Number(holes))));
        assert.equal(new Set(matches.map(o => o.id)).size, matches.length);
      }
    }
  }
});

test('missing dates and invalid filters never substitute another date', () => {
  assert.deepEqual(filterSnapshot(undefined, '00:00', '23:59', 1, 'any'), []);
  for (const players of [0, 5, NaN, 1.5]) assert.deepEqual(filterSnapshot(data[0], '00:00', '23:59', players, 'any'), []);
  assert.deepEqual(filterSnapshot(data[0], '17:00', '06:00', 1, 'any'), []);
});

test('published snapshot bundle has labelled provenance and clean provider links', () => {
  assert.ok(data.length >= 2);
  assert.ok(data.reduce((total, s) => total + s.offers.length, 0) >= 20);
  for (const snapshot of data) {
    assert.equal(snapshot.kind, 'snapshot');
    assert.equal(snapshot.timezone, 'Australia/Melbourne');
    assert.ok(Number.isFinite(Date.parse(snapshot.captured_at)));
    for (const offer of snapshot.offers) {
      const url = new URL(offer.booking_url);
      assert.equal(url.origin, 'https://freeway.quick18.com');
      assert.deepEqual([...url.searchParams.keys()], ['psid', 'p']);
    }
  }
});
