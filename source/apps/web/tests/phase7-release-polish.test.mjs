import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(here, "..");
const read = (path) => readFileSync(resolve(webRoot, path), "utf8");

test("sign-in uses customer-friendly messages and does not blame every failure on the password", () => {
  const login = read("app/login/page.tsx");
  const api = read("lib/api.ts");
  assert.match(login, /We couldn't sign you in/);
  assert.match(api, /We couldn't sign you in\. Check your email and password, then try again\./);
  assert.match(api, /NO_ACTIVE_WORKSPACE/);
  assert.doesNotMatch(api, /doesn't match an account/);
});

test("settings edits real business profile values instead of showing a roadmap", () => {
  const settings = read("app/settings/page.tsx");
  assert.match(settings, /getBusinessProfile/);
  assert.match(settings, /createBusinessProfile/);
  assert.match(settings, /updateBusinessProfile/);
  assert.match(settings, /Save business details/);
  assert.match(settings, /role="alert"/);
  assert.doesNotMatch(settings, /Planned depth|Next vertical|will be implemented|Workspace foundation/i);
});

test("business insights use saved sales and inventory information with clear empty and error states", () => {
  const insights = read("app/intelligence/page.tsx");
  assert.match(insights, /getAnalyticsOverview/);
  assert.match(insights, /getInventorySummary/);
  assert.match(insights, /getInventoryReplenishmentRecommendations/);
  assert.match(insights, /No restock suggestions to show/);
  assert.match(insights, /Some information is unavailable/);
  assert.match(insights, /do not place orders automatically/);
  assert.doesNotMatch(insights, /Planned depth|Next vertical|will be implemented/i);
});

test("navigation has a usable destination for Business insights and contains no stale app version", () => {
  const shell = read("components/app-shell.tsx");
  assert.match(shell, /\["\/intelligence", "Business insights"/);
  assert.match(shell, /Business insights/);
  assert.doesNotMatch(shell, /v2\.9\.0/);
  assert.match(shell, /saved business records/);
});

test("customer pages do not contain the removed foundation placeholder", () => {
  assert.equal(existsSync(resolve(webRoot, "components/module-foundation.tsx")), false);
  const purchasing = read("app/purchasing/page.tsx");
  assert.match(purchasing, /Orders are prepared for your team to review/);
  assert.doesNotMatch(purchasing, /Phase 7 controls:/);
});
