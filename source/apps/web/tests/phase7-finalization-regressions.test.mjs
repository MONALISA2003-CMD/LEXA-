import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(here, "..");
const inventory = readFileSync(resolve(webRoot, "app/inventory/page.tsx"), "utf8");
const purchasing = readFileSync(resolve(webRoot, "app/purchasing/page.tsx"), "utf8");

test("inventory ledger supplies currency when rendering movement unit costs", () => {
  assert.match(inventory, /money\(row\.unit_cost,\s*businessCurrency\)/);
});

test("supplier return credit estimate falls back to the business currency", () => {
  assert.match(purchasing, /money\(r\.return_value,\s*r\.currency_code\?\?businessCurrency\)/);
});
