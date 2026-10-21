import fs from "node:fs";
import assert from "node:assert/strict";

const source = fs.readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");

// Each dashboard resource must settle independently so one failure cannot erase
// valid results from unrelated business panels.
for (const state of ["dashboardState", "analyticsState", "productsState", "inventorySummaryState", "adjustmentsState", "countsState", "transfersState", "readinessState"]) {
  assert.match(source, new RegExp(`\\[${state}, set${state[0].toUpperCase()}${state.slice(1)}\\] = useState<LoadState>`));
}
assert.equal((source.match(/\.catch\(\(\) =>/g) || []).length, 9, "all eight dashboard resources plus the currency source must handle failures independently");
assert.match(source, /Exception list is incomplete/);
assert.match(source, /inventorySummaryState === "error" \|\| adjustmentsState === "error"/);
assert.match(source, /analyticsState === "error" \|\| !analytics/);
assert.match(source, /inventorySummaryState === "error" \|\| !inventorySummary \? "Unavailable"/);
assert.doesNotMatch(source, /loadError/);
console.log("Command Centre independent panel resilience: PASS");
