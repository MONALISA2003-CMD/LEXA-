import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { primaryNavigation, resolveBusinessSearchDestination } from '../lib/navigation.mjs';

const ROOT = resolve(import.meta.dirname, '..');
const read = (path) => readFile(resolve(ROOT, path), 'utf8');

test('navigation uses plain labels and preserves routes', () => {
  assert.ok(primaryNavigation.some(([href, label]) => href === '/ai-assistant' && label === 'Business assistant'));
  assert.ok(primaryNavigation.some(([href, label]) => href === '/commerce' && label === 'Checkout'));
  assert.ok(primaryNavigation.some(([href, label]) => href === '/daily-brief' && label === 'Daily overview'));
  assert.equal(resolveBusinessSearchDestination('business assistant'), '/ai-assistant?q=business%20assistant');
  assert.equal(resolveBusinessSearchDestination('open checkout'), '/commerce?q=open%20checkout');
});

test('assistant page exposes an interactive LEXA-only chat without browser-side provider access', async () => {
  const page = await read('app/ai-assistant/page.tsx');
  const client = await read('lib/ai-assistant-api.ts');
  assert.match(page, /Your LEXA business assistant/);
  assert.match(page, /Private to your signed-in workspace/);
  assert.match(page, /Your business question/);
  assert.match(page, /<textarea/);
  assert.match(page, /Ask LEXA/);
  assert.match(page, /MarkdownAnswer/);
  assert.doesNotMatch(page, /assistant-provider|Assistant service/);
  assert.match(page, /Clear chat/);
  assert.match(page, /This chat stays in this page and is not saved as conversation history/);
  assert.match(client, /askLexaAssistant/);
  assert.match(client, /\/api\/lexa\/api\/v1\/ai\/assistant/);
  assert.match(client, /Authorization: `Bearer \$\{token\}`/);
  assert.match(client, /include_business_summary: false/);
  assert.doesNotMatch(client, /tenant_id|user_id|workspace_id/);
  assert.doesNotMatch(`${page}\n${client}`, /api\.openai\.com|generativelanguage\.googleapis\.com|api\.groq\.com|NEXT_PUBLIC_[A-Z0-9_]*KEY/i);
  assert.doesNotMatch(page, /The assistant isn’t available right now|This page will not generate or pretend to generate an answer/);
  for (const href of ['/intelligence', '/daily-brief', '/demand-forecast', '/documents', '/reports']) {
    assert.ok(page.includes(`href="${href}"`), `missing business-support link ${href}`);
  }
});

test('daily overview avoids internal table names and external AI provider copy', async () => {
  const page = await read('app/daily-brief/page.tsx');
  assert.match(page, /Daily overview/);
  assert.doesNotMatch(page, /source_tables\.join|saved rows|deterministic rules|external AI provider|model provider/i);
});

test('document review uses plain language and hides technical reading identifiers', async () => {
  const page = await read('app/documents/page.tsx');
  assert.match(page, /Review important details from your documents/);
  assert.match(page, /Check every detail against the original/);
  assert.match(page, /friendlyReadingMethod\(selected\.extraction_method\)/);
  assert.doesNotMatch(page, /branch-scoped store|AI provider|API key|quota|label match/i);
});

test('language standards and inventory are included', async () => {
  const standards = await read('../../docs/LEXA_PRODUCT_LANGUAGE_STANDARDS.md');
  const inventory = await read('../../docs/LEXA_PRODUCT_LANGUAGE_INVENTORY_2026-10-24.md');
  assert.match(standards, /Professional and approachable/);
  assert.match(standards, /financial meaning|accounting records/i);
  assert.match(inventory, /Business assistant/);
  assert.match(inventory, /Tax and receipts/);
});
