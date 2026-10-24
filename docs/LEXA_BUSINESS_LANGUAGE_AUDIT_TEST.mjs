import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const ROOT = resolve(import.meta.dirname, '..');
const read = (path) => readFile(resolve(ROOT, path), 'utf8');

test('navigation uses the words business owners see in daily work', async () => {
  const nav = await read('lib/navigation.mjs');
  const shell = await read('components/app-shell.tsx');
  assert.match(nav, /"Business details"/);
  assert.match(nav, /"Sales forecast"/);
  assert.match(nav, /Sales estimates and restock planning/);
  assert.match(shell, /Business details/);
  assert.doesNotMatch(shell, /Business settings|workspace-wide|RLS|schema migration/);
});

test('stock, products and purchasing use familiar words', async () => {
  const stock = await read('app/inventory/page.tsx');
  const products = await read('app/products/page.tsx');
  const purchasing = await read('app/purchasing/page.tsx');
  assert.match(stock, /Stock history/);
  assert.match(stock, /Restock suggestions/);
  assert.match(products, /product options/i);
  assert.match(purchasing, /Record deliveries/);
  assert.match(purchasing, /Difference to check/);
});

test('sales planning explains estimates without statistical shorthand', async () => {
  const page = await read('app/demand-forecast/page.tsx');
  assert.match(page, /Average forecast error/);
  assert.match(page, /For planning only/);
  assert.match(page, /Past range for the same day of the week/);
  assert.doesNotMatch(page, /rolling-origin|Mean absolute error|\bWAPE\b|Predictive intelligence/);
});

test('the daily overview explains missing information clearly', async () => {
  const page = await read('app/daily-brief/page.tsx');
  assert.match(page, /BUSINESS UPDATES/);
  assert.match(page, /Information to check/);
  assert.match(page, /Missing information is not counted as zero/);
});

test('the business assistant remains honest and does not present a disabled question form', async () => {
  const page = await read('app/ai-assistant/page.tsx');
  assert.match(page, /Guidance that fits your business/);
  assert.match(page, /The business assistant isn’t available right now/);
  assert.match(page, /will not answer questions or change your business records while it is unavailable/);
  assert.doesNotMatch(page, /fetch\(|<textarea|Get guidance|executionAvailable|provider|model selector/i);
});

test('shared messages give the user a next step without technical wording', async () => {
  const ui = await read('components/ui.tsx');
  const api = await read('lib/api.ts');
  assert.match(ui, /No records yet/);
  assert.match(ui, /You cannot open this area/);
  assert.match(api, /Check the record before trying again/);
  assert.doesNotMatch(ui, /stack trace|HTTP status|database schema/i);
});
