import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const webRoot = new URL("../", import.meta.url);
const read = (path) => readFileSync(new URL(path, webRoot), "utf8");
const css = read("app/lexa-brand-authority.css");
const layout = read("app/layout.tsx");
const appShell = read("components/app-shell.tsx");
const home = read("app/page.tsx");
const charts = read("components/dashboard-charts.tsx");
const assets = new URL("public/", webRoot);

const routeFiles = [
  "app/page.tsx", "app/commerce/page.tsx", "app/sales/page.tsx", "app/inventory/page.tsx",
  "app/products/page.tsx", "app/customers/page.tsx", "app/purchasing/page.tsx",
  "app/accounting/page.tsx", "app/reports/page.tsx", "app/daily-brief/page.tsx",
  "app/demand-forecast/page.tsx", "app/intelligence/page.tsx", "app/ai-assistant/page.tsx",
  "app/documents/page.tsx", "app/team-chat/page.tsx", "app/compliance/page.tsx",
  "app/administration/page.tsx", "app/administration/members/page.tsx", "app/settings/page.tsx",
  "app/settings/security/page.tsx", "app/workspace/page.tsx", "app/onboarding/page.tsx",
  "app/login/page.tsx", "app/register/page.tsx", "app/forgot-password/page.tsx", "app/reset-password/page.tsx"
];

test("the unified LEXA plan is applied across every existing business route", () => {
  for (const path of routeFiles) assert.ok(existsSync(new URL(path, webRoot)), `missing frontend route: ${path}`);
  assert.match(appShell, /className="app-shell"/);
  assert.match(appShell, /className="app-brand"/);
  assert.match(home, /SalesTrendChart/);
  assert.match(layout, /lexa-brand-authority\.css/);
});

test("the master logo and one shared palette govern desktop, mobile and authentication", () => {
  for (const asset of ["lexa-master-logo.jpg", "lexa-wordmark-master.jpg", "lexa-app-mark.png"]) {
    assert.ok(existsSync(new URL(asset, assets)), `missing LEXA master asset: ${asset}`);
  }
  for (const token of ["--lexa-midnight: #010D27", "--lexa-blue: #075FE8", "--lexa-cyan: #01B9BB", "--lexa-green: #00B77D", "--lexa-gold: #E1C140", "--lexa-red: #E91D3A"]) {
    assert.ok(css.includes(token), `missing design token ${token}`);
  }
  assert.match(css, /background-image:\s*url\('\/lexa-master-logo\.jpg'\)\s*!important/);
  assert.match(css, /background-image:\s*url\('\/lexa-wordmark-master\.jpg'\)\s*!important/);
  assert.match(css, /\.app-shell \.button-dark[\s\S]*?background:\s*#075FE8\s*!important/);
});

test("dashboard and reports use clear, distinct chart series and an accessible data alternative", () => {
  for (const selector of [".command-kpis", ".phase4-analytics-grid", ".chart-series-sales", ".chart-series-collected", ".product-comparison-track", ".chart-data-table-wrap", ".report-period-presets"]) {
    assert.ok(css.includes(selector), `missing dashboard/report treatment ${selector}`);
  }
  assert.match(charts, /role="img" aria-labelledby=/);
  assert.match(charts, /View daily figures/);
  assert.match(charts, /Missing dates are left blank rather than counted as zero activity/);
});

test("shared workflow UI is legible for tables, forms, statuses and specialist modules", () => {
  for (const selector of [".data-table th", ".command-form input", ".filter-row input", ".status.good", ".status.warn", ".status.danger", "[class*=\"chatShell__\"]", "[class*=\"documentList__\"]", "[class*=\"summaryStats__\"]"]) {
    assert.ok(css.includes(selector), `missing shared UI treatment ${selector}`);
  }
  assert.match(css, /@media \(max-width: 800px\)/);
  assert.match(css, /@media \(max-width: 520px\)/);
  assert.match(css, /@media \(max-width: 350px\)/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /button:focus-visible, a:focus-visible/);
});
