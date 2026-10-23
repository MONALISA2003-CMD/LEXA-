import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { resolveBusinessInsightQuestion } from "../lib/business-insight-question.mjs";

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
