import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { localDateISO, localMonthStartISO } from '../lib/date.mjs';
import { safeReturnPath } from '../lib/navigation.mjs';

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (path) => readFileSync(resolve(webRoot, path), 'utf8');
const css = read('app/globals.css');
const login = read('app/login/page.tsx');
const apiProxy = read('app/api/lexa/[...path]/route.ts');
const commandCentre = read('app/page.tsx');
const reports = read('app/reports/page.tsx');
const accounting = read('app/accounting/page.tsx');
const commerce = read('app/commerce/page.tsx');

function localDateString(year, monthIndex, day, hour = 0, minute = 0) {
  return new Date(year, monthIndex, day, hour, minute);
}

test('calendar defaults use local calendar fields instead of UTC ISO slicing', () => {
  const earlyLocalMorning = localDateString(2026, 9, 1, 0, 30);
  assert.equal(localDateISO(earlyLocalMorning), '2026-10-01');
  assert.equal(localMonthStartISO(earlyLocalMorning), '2026-10-01');
  for (const source of [commandCentre, reports, accounting, commerce]) {
    assert.match(source, /localDateISO/);
    assert.doesNotMatch(source, /toISOString\(\)\.slice\(0,\s*10\)/);
  }
});

test('post-login destination remains within the current origin', () => {
  const origin = 'https://lexa.example';
  assert.equal(safeReturnPath('/inventory?filter=low#results', origin), '/inventory?filter=low#results');
  assert.equal(safeReturnPath('/reports', origin), '/reports');
  assert.equal(safeReturnPath('//outside.example/path', origin), '/');
  assert.equal(safeReturnPath('/\\\\outside.example/path', origin), '/');
  assert.equal(safeReturnPath('https://outside.example/path', origin), '/');
  assert.equal(safeReturnPath(null, origin), '/');
  assert.match(login, /resolveSafeReturnPath\(next, window\.location\.origin\)/);
});

test('auth card uses a stacked tablet layout and visible keyboard focus', () => {
  assert.match(css, /@media\s*\(min-width:\s*601px\)\s*and\s*\(max-width:\s*800px\)/);
  assert.match(css, /\.auth-page\s*\{\s*grid-template-columns:\s*minmax\(0,\s*1fr\)/);
  assert.match(css, /\.auth-form-v2 input:focus-visible/);
  assert.match(css, /\.auth-password-toggle:focus-visible/);
  assert.match(css, /\.auth-password-toggle\s*\{[^}]*min-height:\s*44px/s);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
});

test('session-scoped API proxy responses cannot be cached by intermediaries', () => {
  assert.match(apiProxy, /cache-control",\s*"no-store, max-age=0"/i);
  assert.match(apiProxy, /pragma",\s*"no-cache"/i);
  assert.match(apiProxy, /x-content-type-options",\s*"nosniff"/i);
  assert.match(apiProxy, /responseRequestId \|\| null/);
});

test('Command Centre and Commerce allow the API to select tenant-authoritative business date', () => {
  assert.match(commandCentre, /getCommerceDashboard\(\)/);
  assert.match(commerce, /getCommerceDashboard\(\)/);
});
