import fs from "node:fs";
import assert from "node:assert/strict";

const root = new URL("../", import.meta.url);
const read = (path) => fs.readFileSync(new URL(path, root), "utf8");
const home = read("app/page.tsx");
const api = read("lib/api.ts");
const shell = read("components/app-shell.tsx");
const navigation = read("lib/navigation.mjs");
const styles = read("app/globals.css");
const routeTests = fs.readFileSync(new URL("../../apps/api/tests/test_stage2_cross_module_contracts.py", root), "utf8");

assert.match(home, /A quick look at your money/);
assert.match(home, /Customers who owe you/);
assert.match(home, /Supplier bills to pay/);
assert.match(home, /getPurchasingSummary\(\)/);
assert.match(home, /supplier_balances_by_currency\.find/);
assert.match(home, /purchasingSummaryState === "error".*Unavailable/s);
assert.match(api, /export type PurchasingSummary/);
assert.match(navigation, /Business details/);
assert.match(shell, /Finish business setup/);
assert.match(styles, /--emerald: #10B981/);
assert.match(styles, /--teal: #13B8B0/);
assert.match(styles, /--electric-blue: #496CFF/);
assert.match(styles, /finance-overview-grid/);
assert.match(styles, /focus-visible/);
assert.match(routeTests, /require_full_branch_scope/);
console.log("Stage 2 connected finance overview and Stage 3 Emerald Fusion UI contracts: PASS");

assert.match(home, /Your business is ready/);
assert.match(read("app/purchasing/page.tsx"), /Purchases and suppliers/);
assert.match(read("app/purchasing/page.tsx"), /Confirm delivery and update stock/);
assert.match(read("app/accounting/page.tsx"), /Never enter PINs, passwords, one-time codes or banking sign-in details/);
assert.match(read("app/reports/page.tsx"), /Expenses by category/);
assert.match(read("components/dashboard-charts.tsx"), /aria-label="Expenses by category"/);

assert.match(read("app/reports/page.tsx"), /Money recorded by payment method/);
assert.match(read("app/reports/page.tsx"), /getAnalyticsPaymentsByChannel/);
assert.match(read("components/dashboard-charts.tsx"), /aria-label="Money recorded by payment method"/);
assert.match(read("lib/api.ts"), /payments-by-channel/);
console.log("Payment method reporting contract: PASS");
