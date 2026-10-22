import fs from "node:fs";
import assert from "node:assert/strict";

const root = new URL("../", import.meta.url);
const commerce = fs.readFileSync(new URL("app/commerce/page.tsx", root), "utf8");
const api = fs.readFileSync(new URL("lib/api.ts", root), "utf8");
const styles = fs.readFileSync(new URL("app/globals.css", root), "utf8");

assert.match(commerce, /type CartLine = \{ id:string; variantId:string; quantity:string; unitPrice:string \}/);
assert.match(commerce, /setCart\(\(current\) =>/);
assert.match(commerce, /lines: cart\.map\(/);
assert.match(commerce, /Checkout cart/);
assert.match(commerce, /Payments cannot exceed the checkout total/);
assert.match(commerce, /Ask the business owner or manager before changing it/);
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

console.log("Phase 5 sales cockpit, multi-line checkout, filtered history, idempotent retry and receipt contracts: PASS");
