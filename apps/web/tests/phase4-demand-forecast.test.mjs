import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '..');
const page = readFileSync(path.join(web, 'app', 'demand-forecast', 'page.tsx'), 'utf8');
const client = readFileSync(path.join(web, 'lib', 'demand-forecast-api.ts'), 'utf8');
const nav = readFileSync(path.join(web, 'lib', 'navigation.mjs'), 'utf8');
const apiRoutes = readFileSync(path.resolve(web, '..', 'api', 'app', 'intelligence', 'routes.py'), 'utf8');
const forecast = readFileSync(path.resolve(web, '..', 'api', 'app', 'intelligence', 'forecasting.py'), 'utf8');

test('demand forecast is discoverable from navigation and natural-language search', () => {
  assert.match(nav, /\["\/demand-forecast", "Sales forecast", "chart"\]/);
  assert.match(nav, /Expected demand and sales forecast/);
  assert.match(nav, /"\/demand-forecast"/);
});

test('forecast client is authenticated, read-only and rejects out-of-range horizons', () => {
  assert.match(client, /getCachedSession\(\) \|\| await restoreSession\(\)/);
  assert.match(client, /\/api\/lexa\/api\/v1\/intelligence\/demand-forecast/);
  assert.match(client, /Authorization: `Bearer \$\{token\}`/);
  assert.match(client, /horizonDays < 7 \|\| horizonDays > 28/);
  assert.match(client, /cache: "no-store"/);
  assert.doesNotMatch(client, /method:\s*["']POST|method:\s*["']PUT|method:\s*["']PATCH|method:\s*["']DELETE/);
});

test('forecast UI discloses uncertainty and does not offer a transaction/write action', () => {
  assert.match(page, /Planning evidence only/);
  assert.match(page, /stockouts/);
  assert.match(page, /rolling-origin/);
  assert.match(page, /WAPE/);
  assert.match(page, /Business writes performed: no/);
  assert.match(page, /Open stock/);
  assert.doesNotMatch(page, /createPurchaseOrder|postPurchaseReceipt|createInventoryAdjustment/);
});

test('server requires a fresh full history and disables forecasts when the coverage gate fails', () => {
  assert.match(apiRoutes, /completed_at >= now\(\) - INTERVAL '72 hours'/);
  assert.match(apiRoutes, /from_date <= :history_start/);
  assert.match(apiRoutes, /to_date >= :business_date/);
  assert.match(apiRoutes, /FRESH_COMPLETE_HISTORY_REQUIRED/);
  assert.match(apiRoutes, /require_full_branch_scope/);
  assert.match(apiRoutes, /business_writes_performed/);
  assert.match(forecast, /rolling-origin/);
  assert.match(forecast, /MIN_ACTIVE_DEMAND_DAYS/);
  assert.match(forecast, /wape_unavailable_when_test_actuals_are_zero/);
});
