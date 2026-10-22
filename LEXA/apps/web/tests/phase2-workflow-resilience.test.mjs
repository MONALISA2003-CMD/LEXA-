import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const commandCentre = readFileSync(resolve(root, 'app/page.tsx'), 'utf8');
const products = readFileSync(resolve(root, 'app/products/page.tsx'), 'utf8');
const inventory = readFileSync(resolve(root, 'app/inventory/page.tsx'), 'utf8');
const api = readFileSync(resolve(root, 'lib/api.ts'), 'utf8');
const render = readFileSync(resolve(root, '../../render.yaml'), 'utf8');
const catalogRoute = readFileSync(resolve(root, '../../apps/api/app/routes/catalog.py'), 'utf8');

test('Command Centre protects every nullable dashboard and analytics dereference', () => {
  assert.match(commandCentre, /dashboardState === "error" \|\| !dashboard \? "Unavailable"/);
  assert.match(commandCentre, /dashboardState === "error" \|\| !dashboard \? "Sales data could not be loaded"/);
  assert.match(commandCentre, /dashboardState === "error" \|\| !dashboard \? "Payment data could not be loaded"/);
  assert.match(commandCentre, /analyticsState === "error" \|\| !analytics \? "Unavailable"/);
  assert.match(commandCentre, /analyticsState === "error" \|\| !analytics \? "Reporting data could not be loaded"/);
});


test('Command Centre guards descriptions as well as KPI values for nullable data', () => {
  const salesKpis = commandCentre.split('\n').filter((line) => line.includes('className="command-kpi"') && line.includes('dashboard.sales.'));
  const analyticsKpi = commandCentre.split('\n').find((line) => line.includes('className="command-kpi"') && line.includes('analytics.totals.'));
  assert.equal(salesKpis.length, 2, 'expected both sales KPI rows');
  for (const line of salesKpis) {
    const guardCount = (line.match(/dashboardState === "error" \|\| !dashboard \?/g) || []).length;
    assert.equal(guardCount, 2, 'each sales KPI must guard its value and description');
  }
  assert.ok(analyticsKpi, 'expected analytics KPI row');
  const analyticsGuardCount = (analyticsKpi.match(/analyticsState === "error" \|\| !analytics \?/g) || []).length;
  assert.equal(analyticsGuardCount, 2, 'analytics KPI must guard both metric value and description');
});

test('Product catalogue search cancels stale requests and rejects late results', () => {
  assert.match(products, /const productRequestId = useRef\(0\)/);
  assert.match(products, /getProducts\(normalized, signal\)/);
  assert.match(products, /signal\?\.aborted \|\| requestId !== productRequestId\.current/);
  assert.match(products, /clearTimeout\(timer\); controller\.abort\(\)/);
  assert.doesNotMatch(products, /Promise\.all\(\[getProducts\(search\), getCategories\(\), getBrands\(\), getUnits\(\), getPriceLists\(\)\]\)/);
});

test('Product search supports product codes and barcodes without mutating catalogue records', () => {
  assert.match(products, /getCatalogLookup\(normalized, signal\)/);
  assert.match(products, /missingProductIds.*slice\(0, 10\)/s);
  assert.match(products, /Promise\.allSettled\(missingProductIds\.map\(\(id\) => getProduct\(id, signal\)\)\)/);
  assert.match(api, /export function getCatalogLookup\(query: string, signal\?: AbortSignal\)/);
  assert.match(api, /export function getProduct\(productId: string, signal\?: AbortSignal\)/);
  assert.match(catalogRoute, /@router\.get\("\/lookup", response_model=list\[dict\]\)/);
  assert.match(catalogRoute, /ProductVariant\.sku\.ilike/);
  assert.match(catalogRoute, /Barcode\.barcode == needle/);
  assert.match(products, /Search product name, product code or barcode/);
});

test('Inventory filters refresh only balance and ledger data with cancellation and stale-result protection', () => {
  assert.match(inventory, /const firstFilterEffect = useRef\(true\)/);
  assert.match(inventory, /const stockRequestId = useRef\(0\)/);
  assert.match(inventory, /new AbortController\(\)/);
  assert.match(inventory, /getInventoryBalances\([\s\S]*controller\.signal\)/);
  assert.match(inventory, /getInventoryLedger\([\s\S]*controller\.signal\)/);
  assert.match(inventory, /requestId !== stockRequestId\.current/);
  assert.match(inventory, /setFiltersBusy\(true\)/);
  assert.match(inventory, /metricUnavailable = !hasLoaded \|\| busy \|\| filtersBusy/);
  assert.match(inventory, /clearTimeout\(timer\); controller\.abort\(\)/);
  assert.match(api, /getInventoryBalances\([^\n]*signal\?: AbortSignal\)/);
  assert.match(api, /getInventoryLedger\([^\n]*signal\?: AbortSignal\)/);
});

test('Render blueprint distinguishes liveness from dependency readiness', () => {
  assert.match(render, /healthCheckPath: \/ready/);
  const health = readFileSync(resolve(root, '../../apps/api/app/main.py'), 'utf8');
  assert.match(health, /@app\.get\("\/health"/);
  assert.match(health, /@app\.get\("\/ready"/);
});
