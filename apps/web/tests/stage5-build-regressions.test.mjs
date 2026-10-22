import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const read = (path) => readFileSync(resolve(webRoot, path), "utf8");

test("production build regressions stay fixed for settled promises and supplier bill variance", () => {
  const accounting = read("app/accounting/page.tsx");
  const customers = read("app/customers/page.tsx");
  const purchasing = read("app/purchasing/page.tsx");
  const api = read("lib/api.ts");

  assert.ok(accounting.includes("const reconciliationResult = results[3]"));
  assert.ok(accounting.includes("const accountResult = results[5]"));
  assert.ok(!accounting.includes("results[3].value.some"));
  assert.ok(!accounting.includes("results[5].value.find"));

  assert.ok(customers.includes("const customerResult = results[0]"));
  assert.ok(customers.includes("const receivableResult = results[1]"));
  assert.ok(customers.includes("const profileResult = results[2]"));
  assert.ok(customers.includes("profileResult.value?.currency_code"));
  assert.ok(!customers.includes("results[0].value[0]"));
  assert.ok(!customers.includes("results[1].reason"));
  assert.ok(!customers.includes("results[2].value.currency_code"));

  assert.ok(api.includes("match_variance?: string"));
  assert.ok(purchasing.includes("b.match_variance"));
  assert.ok(!purchasing.includes("match_difference"));
});
