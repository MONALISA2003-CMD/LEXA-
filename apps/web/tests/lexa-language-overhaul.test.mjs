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

test('assistant page shows a useful unavailable state without provider setup', async () => {
  const page = await read('app/ai-assistant/page.tsx');
  assert.match(page, /The assistant isn’t available right now/);
  for (const phrase of ['API key', 'quota', 'provider', 'OpenAI', 'Gemini', 'Groq', 'paid service', 'NEXT_PUBLIC_', 'model selector']) {
    assert.doesNotMatch(page.toLowerCase(), new RegExp(phrase.toLowerCase()));
  }
  for (const href of ['/sales', '/inventory', '/reports', '/purchasing', '/customers', '/documents']) assert.ok(page.includes(`href: "${href}"`));
  assert.doesNotMatch(page, /fetch\(|<textarea|Get guidance|AI provider/i);
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
