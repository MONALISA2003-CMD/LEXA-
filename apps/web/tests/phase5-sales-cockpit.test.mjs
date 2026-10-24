import fs from "node:fs";
import assert from "node:assert/strict";

const root = new URL("../", import.meta.url);
const commerce = fs.readFileSync(new URL("app/commerce/page.tsx", root), "utf8");
const api = fs.readFileSync(new URL("lib/api.ts", root), "utf8");
const styles = fs.readFileSync(new URL("app/globals.css", root), "utf8");
const acceptance = fs.readFileSync(new URL("e2e/phase5-sales-acceptance.spec.ts", root), "utf8");
const workflow = fs.readFileSync(new URL("../../.github/workflows/lexa-ci.yml", root), "utf8");

assert.match(commerce, /type CartLine = \{ id:string; variantId:string; quantity:string; unitPrice:string; discountAmount:string \}/);
assert.match(commerce, /setCart\(\(current\) =>/);
assert.match(commerce, /lines: cart\.map\(/);
assert.match(commerce, /discount_amount: line\.discountAmount/);
assert.match(commerce, /can_manage_sales/);
assert.match(commerce, /Manager permission required/);
assert.match(commerce, /Checkout cart/);
assert.match(commerce, /Payments cannot exceed the checkout total/);
assert.match(commerce, /Catalogue price is locked for your role/);
assert.match(commerce, /Select a customer to record an outstanding balance/);
assert.match(commerce, /lastCheckoutAttempt\?\.fingerprint === fingerprint/);
assert.match(commerce, /createCommerceSale\(body, attempt\.key\)/);
assert.match(commerce, /Search products/);
assert.match(commerce, /Search customer or sale reference/);
assert.match(commerce, /start_date: salesStartDate/);
assert.match(commerce, /end_date: salesEndDate/);
assert.match(commerce, /branch_id: salesBranchId/);
assert.match(commerce, /View sale/);
assert.match(commerce, /window\.print\(\)/);
assert.match(commerce, /moneyInWorkspace = \(value: string \| number\) => money\(value, currencyCode\)/);
assert.match(commerce, /currency_code: currencyCode/);
assert.match(api, /export type CommerceSalesQuery/);
assert.match(api, /Idempotency-Key':idempotencyKey \|\| key\(\)/);
assert.match(styles, /\.sales-history-filters/);
assert.match(styles, /@media print/);
assert.doesNotMatch(commerce, /await setReconciliationActual\(line\.line_id, \{ actual_amount: value \}\);\s*await setReconciliationActual/);
assert.match(acceptance, /disposable_scope === true/);
assert.match(acceptance, /reset_strategy === 'dispose_test_tenant'/);
assert.match(acceptance, /knownProductionHosts\.has\(baseHost\)/);
assert.match(acceptance, /\/api\/lexa\/ready/);
assert.match(acceptance, /entry_role === 'SALE_RECOGNITION'/);
assert.match(acceptance, /journal\.lines\.every\(line => line\.currency_code === data\.currency_code\)/);
assert.match(acceptance, /expect\(debit\)\.toBeCloseTo\(credit, 4\)/);

// Default CI intentionally stays lightweight. Write-enabled, disposable-staging
// acceptance and clean PostgreSQL replay are separate release gates, not CI defaults.
assert.match(workflow, /name: LEXA Main Build CI/);
assert.match(workflow, /api-unit-contracts:/);
assert.match(workflow, /web-build:/);
assert.match(workflow, /compose-config:/);
assert.doesNotMatch(workflow, /run_phase345_staging_e2e/);
assert.doesNotMatch(workflow, /LEXA_PHASE345_STAGING_URL/);
assert.doesNotMatch(workflow, /clean-database-replay/);

console.log("Phase 5 sales cockpit, checkout, journal evidence and lightweight CI contracts: PASS");
