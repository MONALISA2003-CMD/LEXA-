import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const webRoot = new URL("../", import.meta.url);
const read = (path) => readFileSync(new URL(path, webRoot), "utf8");
const css = read("app/lexa-brand-authority.css");
const layout = read("app/layout.tsx");
const home = read("app/page.tsx");
const chart = read("components/dashboard-charts.tsx");
const shell = read("components/app-shell.tsx");
const assets = new URL("public/", webRoot);

test("master LEXA assets are canonical and used in global metadata", () => {
  for (const name of ["lexa-master-logo.jpg", "lexa-wordmark-master.jpg", "lexa-app-mark.png", "lexa-logo.svg", "lexa-logo-light.svg", "lexa-mark.svg"]) {
    assert.ok(existsSync(new URL(name, assets)), `missing official asset ${name}`);
  }
  assert.match(layout, /lexa-mark\.svg/);
  assert.match(layout, /Sales · Inventory · Business Management/);
  assert.match(css, /background-image:\s*url\('\/lexa-wordmark-master\.jpg'\)/);
  assert.match(css, /background-image:\s*url\('\/lexa-master-logo\.jpg'\)/);
});

test("one shared colour authority governs brand, interactions, and states", () => {
  for (const pair of ["--lexa-midnight: #010D27", "--lexa-blue: #075FE8", "--lexa-cyan: #01B9BB", "--lexa-green: #00B77D", "--lexa-gold: #E1C140", "--lexa-red: #E91D3A"]) assert.ok(css.includes(pair), `missing ${pair}`);
  assert.match(css, /\.button-dark,\.primary,\.auth-submit\s*\{[^}]*background:#075FE8/s);
  assert.match(css, /\.chart-series-sales\s*\{\s*stroke:#075FE8/);
  assert.match(css, /\.chart-series-collected\s*\{\s*stroke:#087F91/);
});

test("dashboard and graph treatments use real figures, accessible chart series and detail tables", () => {
  for (const selector of [".command-toolbar", ".command-kpis", ".phase4-analytics-grid", ".trend-panel", ".top-products-panel", ".chart-summary-row", ".sales-trend-svg", ".chart-data-details", ".product-comparison-track", ".chart-data-table-wrap"]) assert.ok(css.includes(selector), `missing ${selector}`);
  assert.match(home, /SalesTrendChart/);
  assert.match(chart, /role="img" aria-labelledby=/);
  assert.match(chart, /View daily figures/);
  assert.match(chart, /Missing dates are left blank rather than counted as zero activity/);
});

test("shared brand coverage includes all module families and specialised CSS modules", () => {
  for (const selector of [".app-sidebar", ".app-nav-item.active", ".mobile-nav", ".data-table th", ".auth-card", "[class*=\"chatShell__\"]", "[class*=\"documentList__\"]", "[class*=\"summaryStats__\"]"]) assert.ok(css.includes(selector), `missing ${selector}`);
  assert.match(shell, /app-brand/);
});

test("mobile, touch, keyboard, and reduced motion are covered", () => {
  assert.match(css, /@media \(max-width: 800px\)/);
  assert.match(css, /@media \(max-width: 520px\)/);
  assert.match(css, /@media \(max-width: 350px\)/);
  assert.match(css, /prefers-reduced-motion:reduce/);
  assert.match(css, /button:focus-visible,a:focus-visible/);
});
