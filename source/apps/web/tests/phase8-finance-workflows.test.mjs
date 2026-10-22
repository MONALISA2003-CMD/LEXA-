import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(here, "..");
const read = (path) => readFileSync(resolve(webRoot, path), "utf8");

test("Finance page uses plain-language payment, expense and balance workflows", () => {
  const page = read("app/accounting/page.tsx");
  assert.match(page, /Payment methods/);
  assert.match(page, /Customer balances/);
  assert.match(page, /End-of-day check/);
  assert.match(page, /Add an expense/);
  assert.match(page, /Money recorded as received/);
  assert.match(page, /Cost of products sold/);
  assert.match(page, /Sales after product costs/);
  assert.doesNotMatch(page, /Trial balance|journal entries|post expense/i);
});

test("payment recording explicitly does not connect to providers or store credentials", () => {
  const page = read("app/accounting/page.tsx");
  const api = read("lib/api.ts");
  assert.match(page, /does not move money or confirm payments with MTN, Airtel or a bank/i);
  assert.match(page, /Never enter PINs, passwords, one-time codes or account sign-in details/i);
  assert.match(page, /LEXA records what you enter; it does not confirm this payment with a bank or mobile-money provider/i);
  assert.match(api, /deactivatePaymentChannel/);
  assert.doesNotMatch(page, /API key input|password input|PIN input|gateway credentials/i);
});

test("payment methods can be deactivated without deleting historical records", () => {
  const api = read("lib/api.ts");
  const page = read("app/accounting/page.tsx");
  assert.match(api, /\/payment-channels\/\$\{encodeURIComponent\(id\)\}\/deactivate/);
  assert.match(page, /Past payments will remain in your history/);
  assert.match(page, /Existing payments and reports are kept/);
});

test("expense lifecycle supports draft, official record, cancellation and correction", () => {
  const api = read("lib/api.ts");
  const page = read("app/accounting/page.tsx");
  assert.match(api, /export function createExpense/);
  assert.match(api, /export function postExpense/);
  assert.match(api, /export function voidExpense/);
  assert.match(api, /export function reverseExpense/);
  assert.match(page, /Save expense draft/);
  assert.match(page, /Add to business records/);
  assert.match(page, /Cancel draft/);
  assert.match(page, /Correct this expense/);
  assert.match(page, /The original record remains in history|The earlier entry remains available in its history/);
});

test("cash check describes manually entered actual amounts and differences", () => {
  const page = read("app/accounting/page.tsx");
  assert.match(page, /Compare payments recorded in LEXA with the receipts your team counted or found in statements/);
  assert.match(page, /LEXA does not connect to or verify wallets or bank accounts/);
  assert.match(page, /Difference/);
  assert.match(page, /Finish end-of-day check/);
});

test("Phase 8 writes reuse the same key after an uncertain response", () => {
  const api = read("lib/api.ts");
  assert.match(api, /const pendingIdempotencyKeys = new Map/);
  assert.match(api, /pendingIdempotencyKeys\.get\(fingerprint\) \|\| key\(\)/);
  assert.match(api, /Keep the key for network and server failures where the commit result may be unknown/);
  assert.match(api, /export function createExpense\([^\n]+postIdempotent/);
  assert.match(api, /export function payReceivable\([^\n]+postIdempotent/);
});


test("expense history is readable in everyday language and refreshed after changes", () => {
  const page = read("app/accounting/page.tsx");
  const api = read("lib/api.ts");
  assert.match(page, /View history/);
  assert.match(page, /Draft saved/);
  assert.match(page, /Expense added to the business records/);
  assert.match(page, /Expense corrected/);
  assert.match(api, /export function getExpenseHistory/);
  assert.match(page, /setExpenseHistory\(current => \{ const next = \{ \.\.\.current \}; delete next\[expense\.id\]/);
});
