import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const read = (relative) => readFileSync(resolve(here, relative), 'utf8');

test('exact metric questions resolve through local permission-checked LEXA sources', () => {
  const assistant = read('../../api/app/routes/ai_assistant.py');
  assert.match(assistant, /require_full_branch_scope\(db, tenant_id=tenant_id, user_id=user_id\)/);
  assert.match(assistant, /public\.analytics_daily_business_metrics/);
  assert.match(assistant, /public\.analytics_product_daily_metrics/);
  assert.match(assistant, /public\.analytics_inventory_health_metrics/);
  assert.match(assistant, /completed_at >= now\(\) - INTERVAL '72 hours'/);
  assert.match(assistant, /source_mode="local_business_data"/);
  assert.match(assistant, /has not assumed that the value was zero/);
  assert.match(assistant, /fact_answer = _business_fact_answer/);
  assert.match(assistant, /Exact figures are retrieved locally from permission-checked projections/);
});

test('assistant reply reports source mode, response time and evidence without exposing provider choice in UI', () => {
  const api = read('../lib/ai-assistant-api.ts');
  const page = read('../app/ai-assistant/page.tsx');
  assert.match(api, /source_mode: "local_guidance" \| "local_business_data" \| "external_question_only"/);
  assert.match(api, /response_time_ms: number \| null/);
  assert.match(api, /evidence: AssistantEvidence \| null/);
  assert.match(page, /Based on saved LEXA business records/);
  assert.match(page, /Saved figures could not be verified/);
  assert.match(page, /responseMeta/);
  assert.match(page, /message\.evidenceHref/);
  assert.doesNotMatch(page, /message\.provider|message\.model/);
});
