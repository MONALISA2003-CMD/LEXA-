import test from "node:test";
import fs from "node:fs";
import assert from "node:assert/strict";

const root = new URL("../", import.meta.url);
const reports = fs.readFileSync(new URL("app/reports/page.tsx", root), "utf8");
const commerce = fs.readFileSync(new URL("app/commerce/page.tsx", root), "utf8");
const inventory = fs.readFileSync(new URL("app/inventory/page.tsx", root), "utf8");
const api = fs.readFileSync(new URL("lib/api.ts", root), "utf8");
const inventoryRoute = fs.readFileSync(new URL("../../../apps/api/app/routes/inventory.py", import.meta.url), "utf8");
const products = fs.readFileSync(new URL("app/products/page.tsx", root), "utf8");
const dashboard = fs.readFileSync(new URL("app/page.tsx", root), "utf8");
const commercePage = fs.readFileSync(new URL("app/commerce/page.tsx", root), "utf8");
const accounting = fs.readFileSync(new URL("app/accounting/page.tsx", root), "utf8");
const charts = fs.readFileSync(new URL("components/dashboard-charts.tsx", root), "utf8");
const apiRoutes = fs.readFileSync(new URL("../../../apps/api/app/routes/analytics.py", import.meta.url), "utf8");

test("Phase 4 reports apply a validated range, use workspace currency and distinguish unavailable from zero", () => {
  assert.match(reports, /Apply period/);
  assert.match(reports, /nextFrom > nextTo/);
  assert.match(reports, /getBusinessProfile\(\)/);
  assert.match(reports, /currency: currencyCode/);
  assert.match(reports, /Source data was not confirmed/);
  assert.match(reports, /All-time customer history; not filtered by the selected period/);
  assert.match(reports, /Current inventory snapshot; not historical at the selected period/);
  assert.match(reports, /No records for the selected reporting period/);
});

test("Phase 5 returns can submit multiple sale lines and let the server enforce remaining quantities", () => {
  assert.match(commerce, /returnQuantities/);
  assert.match(commerce, /enteredLines\.map\(\(line\) => \(\{ sale_line_id: line\.sale_line_id, quantity: returnQuantities\[line\.sale_line_id\] \}\)\)/);
  assert.match(commerce, /Previously returned quantity is also checked by the server/);
  assert.match(commerce, /Items and return quantities/);
  assert.doesNotMatch(commerce, /setReturnLineId|returnLineId|returnQty/);
});

test("Phase 6 exposes age bands, unknown provenance and reconciliation status end-to-end", () => {
  assert.match(inventory, /"Stock Age"/);
  assert.match(inventory, /getInventoryAgeing/);
  assert.match(inventory, /Over 90d/);
  assert.match(inventory, /UNKNOWN AGE/);
  assert.match(inventory, /RECONCILE/);
  assert.match(api, /\/api\/v1\/inventory\/ageing/);
  assert.match(api, /aged_over_30/);
  assert.match(api, /unknown_age_quantity/);
});

test("Phase 6 stock health surfaces stockout and slow-movement exceptions from completed sales and returns", () => {
  assert.match(inventoryRoute, /@router.get\("\/movement-health"\)/);
  assert.match(inventoryRoute, /OUT_OF_STOCK_WITH_RECENT_DEMAND/);
  assert.match(inventoryRoute, /NO_SALE_90D/);
  assert.match(inventoryRoute, /units_sold_30d/);
  assert.match(inventoryRoute, /units_returned_30d/);
  assert.match(inventory, /Stock Health/);
  assert.match(inventory, /No completed sale found/);
});


test("Phase 4 inventory and product monetary displays never silently assume UGX", () => {
  assert.match(inventory, /getBusinessProfile\(\)/);
  assert.match(inventory, /Currency unavailable/);
  assert.match(products, /getBusinessProfile\(\)/);
  assert.match(products, /Currency unavailable/);
  assert.match(products, /style: "currency", currency,/);
  for (const source of [dashboard, commercePage, accounting, charts]) {
    assert.match(source, /Currency unavailable/);
    assert.doesNotMatch(source, /currencyCode\s*=\s*"UGX"|currency:\s*"UGX"/);
  }
  assert.match(dashboard, /getBusinessProfile\(\)/);
  assert.match(commercePage, /getBusinessProfile\(\)/);
  assert.match(accounting, /getBusinessProfile\(\)/);
  assert.match(apiRoutes, /currency_code: str = Query\(\.\.\./);
  assert.doesNotMatch(apiRoutes, /currency_code: str = Query\(default="UGX"/);
});
