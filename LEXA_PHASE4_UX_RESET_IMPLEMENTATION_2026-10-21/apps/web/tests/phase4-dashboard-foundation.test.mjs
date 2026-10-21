import fs from "node:fs";
import assert from "node:assert/strict";

const root = new URL("../", import.meta.url);
const page = fs.readFileSync(new URL("app/page.tsx", root), "utf8");
const chart = fs.readFileSync(new URL("components/dashboard-charts.tsx", root), "utf8");
const styles = fs.readFileSync(new URL("app/globals.css", root), "utf8");

assert.match(page, /type DashboardPeriod = "7d" \| "30d" \| "90d"/);
assert.match(page, /getAnalyticsOverview\(range\.start, range\.end\)/);
assert.match(page, /getAnalyticsProductSummary\(range\.start, range\.end\)/);
assert.match(page, /aria-pressed=\{analyticsPeriod === period\}/);
assert.match(page, /different business measures, shown together without treating them as interchangeable/i);
assert.match(page, /Missing is not zero/);
assert.match(page, /gross margin/i);
assert.match(chart, /role="img" aria-labelledby=/);
assert.match(chart, /View the underlying daily data/);
assert.match(chart, /contiguousSegments/);
assert.match(chart, /Gaps in returned dates are left as gaps/);
assert.match(chart, /<th scope="col">Net sales<\/th>/);
assert.match(styles, /@media \(max-width: 520px\)/);
assert.match(styles, /prefers-reduced-motion: reduce/);
assert.match(styles, /outline: 3px solid #3155d9/);
console.log("Phase 4 dashboard, analytics-range, chart accessibility and responsive UX contract: PASS");
