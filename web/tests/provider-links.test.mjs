import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/provider-links.ts', import.meta.url), 'utf8');
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { freewayDateUrl } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString('base64')}`);

test('Freeway navigation uses the selected calendar date without tracking tokens', () => {
  assert.equal(freewayDateUrl('2026-10-25'), 'https://freeway.quick18.com/teetimes/searchmatrix?teedate=20261025');
  assert.equal(freewayDateUrl('2028-02-29'), 'https://freeway.quick18.com/teetimes/searchmatrix?teedate=20280229');
});

test('Freeway navigation rejects invalid, empty and injected dates', () => {
  for (const date of ['', '2026-02-29', '2026-13-01', '2026-10-25&x=1', '25/10/2026']) {
    assert.equal(freewayDateUrl(date), null);
  }
});
