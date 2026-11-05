import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const layout = await readFile(new URL('../src/app/layout.tsx', import.meta.url), 'utf8');
const bootstrap = layout.match(/__html:\s*`([^`]+)`/)[1];

function initialTheme(saved, prefersDark, blocked = false) {
  const document = { documentElement: { dataset: {} } };
  vm.runInNewContext(bootstrap, {
    document,
    localStorage: { getItem() { if (blocked) throw new Error('Storage blocked'); return saved; } },
    matchMedia: () => ({ matches: prefersDark }),
  });
  return document.documentElement.dataset.theme;
}

test('saved theme overrides the system preference before the page paints', () => {
  assert.equal(initialTheme('dark', false), 'dark');
  assert.equal(initialTheme('light', true), 'light');
});

test('first visit or an invalid preference follows the system theme', () => {
  assert.equal(initialTheme(null, true), 'dark');
  assert.equal(initialTheme(null, false), 'light');
  assert.equal(initialTheme('invalid', true), 'dark');
});

test('blocked browser storage still produces a usable system theme', () => {
  assert.equal(initialTheme(null, true, true), 'dark');
  assert.equal(initialTheme(null, false, true), 'light');
});
