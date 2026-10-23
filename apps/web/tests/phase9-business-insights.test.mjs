import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { resolveBusinessInsightQuestion } from "../lib/business-insight-question.mjs";
import { buildBusinessInsightAnswer } from "../lib/business-insight-answer.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(here, "..");
const read = (path) => readFileSync(resolve(webRoot, path), "utf8");

test("Phase 9 exposes bounded deterministic insights over canonical source metrics", () => {
  const api = read("lib/api.ts");
  const page = read("app/intelligence/page.tsx");
  assert.match(api, /getBusinessInsights/);
  assert.match(api, /\/api\/v1\/analytics\/insights/);
  assert.match(api, /external_ai_used: false/);
  assert.match(api, /advisory_only: true/);
  assert.match(page, /getBusinessInsights/);
  assert.match(page, /EXPLAINABLE · READ-ONLY/);
  assert.match(page, /How it is calculated/);
  assert.match(page, /Source:/);
  assert.match(page, /Refresh needed/);
  assert.match(page, /Customer & supplier balances/);
  assert.match(page, /Unavailable/);
});

test("Phase 9 keeps suggestions read-only and routes owners to authorized source screens", () => {
  const page = read("app/intelligence/page.tsx");
  const api = read("lib/api.ts");
  assert.match(page, /href="\/reports"/);
  assert.match(page, /href={item\.evidence\.href}/);
  assert.match(page, /do not place orders automatically/);
  assert.match(page, /No external AI provider receives customer or business records/);
  assert.doesNotMatch(api, /openai\.com|api\.anthropic\.com|execute_model_sql|rawSql/);
});


test("Phase 9 question router only selects approved, deterministic insight scopes", () => {
  assert.deepEqual(resolveBusinessInsightQuestion("Why did sales change?"), {
    status: "supported",
    focus: "sales",
    message: "Showing sales movement from saved daily metrics compared with the preceding equal-length period.",
  });
  assert.equal(resolveBusinessInsightQuestion("Is gross margin falling?").focus, "margin");
  assert.equal(resolveBusinessInsightQuestion("Do I have slow-moving stock?").focus, "stock");
  assert.equal(resolveBusinessInsightQuestion("What do customers owe and what do I owe suppliers?").focus, "balances");
  assert.equal(resolveBusinessInsightQuestion("What do I owe suppliers?").focus, "balances");
  assert.equal(resolveBusinessInsightQuestion("Show all insights").focus, "all");
  assert.equal(resolveBusinessInsightQuestion("What is my net profit?").status, "guardrail");
  assert.equal(resolveBusinessInsightQuestion("What is my net profit?").focus, null);
  assert.match(resolveBusinessInsightQuestion("What is my net profit?").message, /not net profit/);
  assert.equal(resolveBusinessInsightQuestion("Who are my top customers?").focus, null);
  assert.match(resolveBusinessInsightQuestion("Who are my top customers?").message, /not guessed/);
  assert.equal(resolveBusinessInsightQuestion("Why did returns increase?").focus, null);
  assert.equal(resolveBusinessInsightQuestion("How much was collected today?").focus, null);
});

test("Phase 9 question UI clearly avoids provider transmission and supports accessible submission", () => {
  const page = read("app/intelligence/page.tsx");
  assert.match(page, /Ask about your saved business figures/);
  assert.match(page, /resolveBusinessInsightQuestion\(question\)/);
  assert.match(page, /business-insight-question-help/);
  assert.match(page, /not sent to an AI provider/);
  const router = read("lib/business-insight-question.mjs");
  assert.match(router, /Gross margin is not net profit/);
});


test("Phase 9 question answer surfaces only the matching saved insight and provenance", () => {
  const sales = {
    id: "sales-movement",
    title: "Sales movement",
    status: "available",
    severity: "attention",
    summary: "Net sales are down 12.50% against the preceding equal-length period.",
    period: { from_date: "2026-10-01", to_date: "2026-10-23" },
    metric: { label: "Net sales", value: "87500.0000", unit: "money", currency_code: "UGX" },
    comparison: { label: "Previous period", previous_value: "100000.0000", change_value: "-12500.0000", change_percent: "-12.50", unit: "money" },
    methodology: "Saved daily metrics, compared with the preceding equal-length period.",
    source: { tables: ["analytics_daily_business_metrics"], record_count: 17, as_of_date: "2026-10-23", refreshed_at: "2026-10-23T11:00:00Z" },
    evidence: { label: "Open sales reports", href: "/reports" },
    limitations: ["A decline alone does not identify the cause."],
  };
  const answer = buildBusinessInsightAnswer("sales", [sales]);
  assert.equal(answer.state, "available");
  assert.equal(answer.title, "Sales movement");
  assert.equal(answer.summary, sales.summary);
  assert.equal(answer.insight.metric.value, "87500.0000");
  assert.equal(answer.insight.source.record_count, 17);
  assert.equal(answer.insight.period.from_date, "2026-10-01");
});

test("Phase 9 question answer treats stale and missing insight data as unverified, not zero", () => {
  const stale = {
    id: "stock-risk", title: "Stock needing attention", status: "stale", severity: "unknown",
    summary: "The latest inventory-health snapshot is too old to support current advice.",
    period: { from_date: "2026-10-20", to_date: "2026-10-23" }, metric: null, comparison: null,
    methodology: "Uses latest saved stock health snapshot.",
    source: { tables: ["analytics_inventory_health_metrics"], record_count: 5, as_of_date: "2026-10-20", refreshed_at: null },
    evidence: { label: "Review stock health", href: "/inventory" }, limitations: ["Refresh the stock snapshot."],
  };
  const staleAnswer = buildBusinessInsightAnswer("stock", [stale]);
  assert.equal(staleAnswer.state, "stale");
  assert.match(staleAnswer.summary, /too old/);
  assert.equal(staleAnswer.insight.metric, null);

  const missingAnswer = buildBusinessInsightAnswer("balances", []);
  assert.equal(missingAnswer.state, "unavailable");
  assert.match(missingAnswer.summary, /business value has been inferred or substituted as zero|not assumed zero|not substituted as zero|not assumed that missing data means zero/i);
  assert.equal(missingAnswer.insight, null);
});

test("Phase 9 overview answer reports coverage instead of inventing a business conclusion", () => {
  const result = buildBusinessInsightAnswer("all", [
    { id: "sales-movement", status: "available" },
    { id: "stock-risk", status: "stale" },
    { id: "working-capital-balances", status: "partial" },
  ]);
  assert.equal(result.state, "overview");
  assert.equal(result.totalCount, 3);
  assert.equal(result.reviewableCount, 2);
  assert.match(result.summary, /3 insights; 2 currently have a reviewable result/);
});

test("Phase 9 visible answer uses the selected saved insight instead of only a generic route message", () => {
  const page = read("app/intelligence/page.tsx");
  assert.match(page, /buildBusinessInsightAnswer/);
  assert.match(page, /ANSWER FROM SAVED RECORDS/);
  assert.match(page, /Source:/);
  assert.match(page, /How it is calculated|Calculation:/);
  assert.match(page, /questionAnswer\.insight\.evidence\.href/);
  assert.match(page, /setQuestionFocus\(null\)/);
  assert.match(page, /setInsightFocus\(result\.focus \?\? "all"\)/);
  assert.match(page, /missing information is not zero/);
});
