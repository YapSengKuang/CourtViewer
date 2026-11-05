import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/format.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { formatUpdated } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);

test('last update shows the actual course-local timestamp and readable age', () => {
  const timestamp = '2026-10-24T01:31:00Z';
  const label = formatUpdated(timestamp, Date.parse('2026-10-24T04:00:00Z'), 'Australia/Melbourne');
  assert.match(label, /^Last updated /);
  assert.match(label, /24 Oct 2026/);
  assert.match(label, /12:31/);
  assert.match(label, /AEDT/);
  assert.match(label, /2 hr ago/);
});

test('ages within a minute and invalid observations are labelled accurately', () => {
  assert.match(formatUpdated('2026-10-24T01:31:00Z', Date.parse('2026-10-24T01:31:20Z')), /just now/);
  assert.match(formatUpdated('2026-10-24T01:31:00Z', Date.parse('2026-10-24T01:32:00Z')), /1 min ago/);
  assert.equal(formatUpdated(null), 'Last update unknown');
  assert.equal(formatUpdated('invalid'), 'Last update unknown');
});
