import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const read = (relative) => readFileSync(resolve(here, relative), 'utf8');

test('external business answers are enabled with privacy-preserving provider defaults', () => {
  const config = read('../../api/app/config.py');
  const assistant = read('../../api/app/routes/ai_assistant.py');
  const client = read('../lib/ai-assistant-api.ts');
  assert.match(config, /lexa_ai_external_providers_enabled:\s*bool\s*=\s*True/);
  assert.match(config, /lexa_ai_allowed_providers:\s*str\s*=\s*"gemini,groq"/);
  assert.match(config, /lexa_ai_paid_providers_enabled:\s*bool\s*=\s*False/);
  assert.match(config, /lexa_ai_aggregates_external_enabled:\s*bool\s*=\s*False/);
  assert.match(assistant, /asyncio\.wait_for\([\s\S]*timeout=12\.0/);
  assert.match(assistant, /httpx\.Timeout\(11\.0, connect=2\.5\)/);
  assert.match(client, /AbortSignal\.timeout\(14_500\)/);
  assert.match(assistant, /includes_business_summary=False/);
  assert.match(assistant, /input_safety_checked=True/);
  assert.match(assistant, /Answer only questions about LEXA usage and business operations/);
  const intelligenceRoutes = read('../../api/app/intelligence/routes.py');
  assert.match(intelligenceRoutes, /eligible_provider_ids_for_question_only/);
  assert.match(intelligenceRoutes, /external_business_assistant/);
  assert.match(assistant, /Do not initiate or claim to initiate payments/);
});

test('URA compliance setup uses verified taxpayer fields and never self-activates EFRIS', () => {
  const page = read('../app/compliance/page.tsx');
  assert.match(page, /id="efris-tin"/);
  assert.match(page, /id="efris-legal-name"/);
  assert.match(page, /id="efris-effective-date"/);
  assert.match(page, /id="efris-status"[\s\S]*readOnly/);
  assert.match(page, /https:\/\/ura\.go\.ug\/en\/efris\/efris-registration\//);
  assert.match(page, /UG_VAT_STANDARD_18/);
  assert.match(page, /UG_VAT_ZERO_RATED_0/);
  assert.match(page, /do not create a default tax rule/i);
  assert.match(page, /FDN/);
});
