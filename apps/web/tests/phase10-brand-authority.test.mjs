import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const webRoot = new URL("../", import.meta.url);
const read = (path) => readFileSync(new URL(path, webRoot), "utf8");
const layout = read("app/layout.tsx");
const brandStyles = read("app/lexa-brand-authority.css");
const publicDir = new URL("public/", webRoot);

test("official LEXA brand assets are present and used globally", () => {
  for (const name of ["lexa-master-logo.jpg", "lexa-wordmark-master.jpg", "lexa-app-mark.png", "lexa-logo.svg", "lexa-logo-light.svg", "lexa-mark.svg"]) {
    assert.ok(existsSync(new URL(name, publicDir)), `missing official brand asset: ${name}`);
  }
  assert.match(layout, /import "\.\/lexa-brand-authority\.css"/);
  assert.match(layout, /LEXA \| Sales · Inventory · Business Management/);
  assert.match(layout, /lexa-app-mark\.png/);
});

test("the master logo governs shell and every authentication journey", () => {
  assert.match(brandStyles, /background-image:\s*url\('\/lexa-wordmark-master\.jpg'\)/);
  assert.match(brandStyles, /background-image:\s*url\('\/lexa-master-logo\.jpg'\)/);
  assert.match(brandStyles, /\.auth-story-brand \.auth-story-logo/);
  assert.match(brandStyles, /\.app-brand \.app-brand-logo/);
});

test("all operation modules inherit one accessible design system", () => {
  for (const token of ["--lexa-midnight", "--lexa-blue", "--lexa-cyan", "--lexa-green", "--lexa-gold", "--lexa-red", "--lexa-border"]) {
    assert.ok(brandStyles.includes(token), `missing brand token ${token}`);
  }
  for (const selector of [".command-kpi", ".app-nav-item.active", ".data-table th", ".finance-overview-card", ".auth-card", ".mobile-nav"]) {
    assert.ok(brandStyles.includes(selector), `missing shared component treatment ${selector}`);
  }
  assert.match(brandStyles, /@media \(max-width: 520px\)/);
  assert.match(brandStyles, /prefers-reduced-motion:\s*reduce/);
});
