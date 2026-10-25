import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { getIntelligencePeriodRange } from "../lib/intelligence-period.mjs";
const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, "..");
const compact = value => ({ fromDate:value.fromDate, toDate:value.toDate, days:value.days, valid:value.valid });
test("period presets use inclusive calendar-day boundaries", () => {
  const today = "2026-10-25";
  assert.deepEqual(compact(getIntelligencePeriodRange("today",today)), {fromDate:"2026-10-25",toDate:"2026-10-25",days:1,valid:true});
  assert.deepEqual(compact(getIntelligencePeriodRange("yesterday",today)), {fromDate:"2026-10-24",toDate:"2026-10-24",days:1,valid:true});
  assert.deepEqual(compact(getIntelligencePeriodRange("this-week",today)), {fromDate:"2026-10-19",toDate:"2026-10-25",days:7,valid:true});
  assert.deepEqual(compact(getIntelligencePeriodRange("last-30-days",today)), {fromDate:"2026-09-26",toDate:"2026-10-25",days:30,valid:true});
});
test("calendar ranges handle year boundaries and leap years", () => {
  assert.deepEqual(compact(getIntelligencePeriodRange("previous-month","2026-01-03")), {fromDate:"2025-12-01",toDate:"2025-12-31",days:31,valid:true});
  assert.deepEqual(compact(getIntelligencePeriodRange("year-to-date","2024-12-31")), {fromDate:"2024-01-01",toDate:"2024-12-31",days:366,valid:true});
});
test("custom ranges reject malformed, reversed and overlong dates", () => {
  assert.equal(getIntelligencePeriodRange("custom","2026-10-25","2026-10-31","2026-10-01").valid,false);
  assert.equal(getIntelligencePeriodRange("custom","2026-10-25","2026-02-30","2026-10-01").valid,false);
  const long = getIntelligencePeriodRange("custom","2026-10-25","2025-10-24","2026-10-25");
  assert.equal(long.valid,false); assert.match(long.error,/366 days or less/);
  assert.equal(getIntelligencePeriodRange("unknown","2026-10-25").valid,false);
});
test("intelligence page connects authorized read-only cross-module data", () => {
  const page = readFileSync(path.join(web,"app","intelligence","page.tsx"),"utf8");
  const api = readFileSync(path.join(web,"lib","api.ts"),"utf8");
  assert.match(page,/getIntelligencePeriodRange/); assert.match(page,/year-to-date/);
  assert.match(page,/Supplier obligations/); assert.match(page,/Customer receivables/);
  assert.match(page,/Branch performance/); assert.match(page,/Gross profit/); assert.match(page,/Customer buying activity/);
  assert.match(api,/\/analytics\/branches\/summary/); assert.match(api,/gross_profit:string\|null/);
  assert.match(api,/\/api\/v1\/intelligence\/business-date/);
  assert.doesNotMatch(page,/method:\s*["']POST|method:\s*["']PUT|method:\s*["']DELETE/);
});
