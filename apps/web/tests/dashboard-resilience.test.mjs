import fs from "node:fs";
import assert from "node:assert/strict";

const source = fs.readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");

// Each dashboard resource must settle independently so one failure cannot erase
// valid results from unrelated business panels.
for (const state of ["dashboardState", "analyticsState", "productsState", "inventorySummaryState", "adjustmentsState", "countsState", "transfersState", "readinessState"]) {
  assert.match(source, new RegExp(`\\[${state}, set${state[0].toUpperCase()}${state.slice(1)}\\] = useState<LoadState>`));
}
assert.equal((source.match(/\.catch\(\(\) =>/g) || []).length, 10, "dashboard resources, supplier balances and currency must handle failures independently; setup is checked by the app shell before this page mounts");
assert.match(source, /Some checks could not be verified/);
assert.match(source, /inventorySummaryState === "error" \|\| adjustmentsState === "error"/);
assert.match(source, /analyticsState === "error" \|\| !analytics/);
assert.match(source, /inventorySummaryState === "error" \|\| !inventorySummary \? "Unavailable"/);
assert.doesNotMatch(source, /loadError/);
assert.match(source, /const lastAnalyticsKey = useRef\(""\)/, "analytics requests should be de-duplicated by refresh, period, tenant business date and currency");
assert.match(source, /if \(lastAnalyticsKey\.current === key\) return;/);
assert.match(source, /operationalRefreshInFlight\.current = false;[\s\S]*setAnalyticsRefreshVersion/);
assert.doesNotMatch(source, /periodEffectMounted/, "the former pair of analytics effects should not race each other");
console.log("Business overview independent panel resilience: PASS");
