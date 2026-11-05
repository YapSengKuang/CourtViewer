import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/collection-schedule.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { nextCollectionTime } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);

test('next scheduled check handles boundaries and day rollover', () => {
  for (const [now, expected] of [
    ['2026-11-04T10:06:59Z', '2026-11-04T10:07:00.000Z'],
    ['2026-11-04T10:07:00Z', '2026-11-04T10:22:00.000Z'],
    ['2026-11-04T10:37:20Z', '2026-11-04T10:52:00.000Z'],
    ['2026-11-04T23:59:59Z', '2026-11-05T00:07:00.000Z'],
  ]) {
    assert.equal(nextCollectionTime(new Date(now)).toISOString(), expected);
  }
});

test('page schedule agrees with hosted and local collection schedules', async () => {
  const workflow = await readFile(new URL('../../.github/workflows/collect.yml', import.meta.url), 'utf8');
  const crontab = await readFile(new URL('../../scraper/crontab.example', import.meta.url), 'utf8');
  assert.match(workflow, /cron: '7,22,37,52 \* \* \* \*'/);
  assert.match(crontab, /^7,22,37,52 \* \* \* \* .*COURSES_YAML=scraper\/courses\.mandalay\.yaml/m);
  const checks = [];
  for (let minute = 0; minute < 60; minute++) {
    const now = new Date(Date.UTC(2026, 10, 4, 10, minute, 59));
    const next = nextCollectionTime(now);
    assert.ok(next > now && next.getTime() - now.getTime() <= 15 * 60 * 1000);
    if (next.getUTCHours() === 10) checks.push(next.getUTCMinutes());
  }
  assert.deepEqual([...new Set(checks)], [7, 22, 37, 52]);
});
