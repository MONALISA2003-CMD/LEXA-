import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const root = new URL("../", import.meta.url);
const read = (path) => readFileSync(new URL(path, root), "utf8");
const css = read("app/lexa-brand-authority.css");
const layout = read("app/layout.tsx");
const publicDir = new URL("public/", root);

function lastRule(selector) {
  const at = css.lastIndexOf(selector);
  assert.notEqual(at, -1, `missing final ${selector} override`);
  const end = css.indexOf("}", at);
  assert.notEqual(end, -1, `unterminated final ${selector} override`);
  return css.slice(at, end + 1);
}

test("desktop sidebar and authentication use the full master artwork", () => {
  assert.ok(existsSync(new URL("lexa-master-logo.jpg", publicDir)));
  assert.ok(existsSync(new URL("lexa-wordmark-master.jpg", publicDir)));
  const sidebar = lastRule(".app-sidebar .app-brand {");
  const auth = lastRule(".auth-story .auth-story-brand {");
  assert.match(sidebar, /background-image:\s*url\('\/lexa-master-logo\.jpg'\)\s*!important/);
  assert.match(auth, /background-image:\s*url\('\/lexa-master-logo\.jpg'\)\s*!important/);
  assert.match(layout, /lexa-brand-authority\.css/);
});

test("mobile header uses the official multicolour wordmark, not the retired compact mark", () => {
  const backgroundAt = css.lastIndexOf("background-image: url('/lexa-wordmark-master.jpg') !important;");
  assert.notEqual(backgroundAt, -1);
  const mobile = css.lastIndexOf(".app-topbar::before {", backgroundAt);
  assert.notEqual(mobile, -1);
  const end = css.indexOf("}", mobile);
  const rule = css.slice(mobile, end + 1);
  assert.match(rule, /content:\s*["']{2}\s*!important/);
  assert.match(rule, /background-image:\s*url\('\/lexa-wordmark-master\.jpg'\)\s*!important/);
  assert.match(rule, /color:\s*transparent\s*!important/);
});

test("the final palette resolves primary buttons to blue while reserving green for positive states", () => {
  const at = css.lastIndexOf(".app-shell .button-dark,");
  assert.notEqual(at, -1);
  const end = css.indexOf("}", at);
  const rule = css.slice(at, end + 1);
  assert.match(rule, /background:\s*#075FE8\s*!important/);
  assert.match(rule, /border-color:\s*#075FE8\s*!important/);
  assert.match(css, /--lexa-green:\s*#00B77D/);
});

test("dashboard KPI hierarchy, report charts and responsive modules have final high-specificity styling", () => {
  for (const token of [
    ".app-content .command-kpi:first-child",
    ".app-content .chart-series-sales",
    ".app-content .chart-series-collected",
    ".app-content .product-comparison-track",
    ".app-shell .app-content [class*=\"chatShell__\"]",
    ".app-shell .app-content [class*=\"documentList__\"]",
    "@media (max-width: 800px)",
    "@media (max-width: 520px)",
    "@media (prefers-reduced-motion: reduce)"
  ]) assert.ok(css.includes(token), `missing final brand contract ${token}`);
});
