import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { applicationRoutes, primaryNavigation, resolveBusinessSearchDestination } from '../lib/navigation.mjs';

const ROOT = resolve(import.meta.dirname, '..');
const read = (path) => readFile(resolve(ROOT, path), 'utf8');

test('documents is a real first-class route and search destination', () => {
  assert.ok(applicationRoutes.includes('/documents'));
  assert.ok(primaryNavigation.some(([href, label]) => href === '/documents' && label === 'Documents'));
  assert.equal(resolveBusinessSearchDestination('upload supplier invoice'), '/documents?q=upload%20supplier%20invoice');
});

test('document API sends authenticated raw bytes and branch/type metadata', async () => {
  const api = await read('lib/document-intelligence-api.ts');
  assert.match(api, /Authorization.*Bearer/);
  assert.match(api, /"Content-Type": file\.type/);
  assert.match(api, /"X-Document-Type": documentType/);
  assert.match(api, /"X-Branch-ID": branchId/);
  assert.match(api, /body: file/);
  assert.match(api, /10 \* 1024 \* 1024/);
  assert.match(api, /application\/pdf.*image\/jpeg.*image\/png.*image\/webp/s);
});

test('document workspace exposes review rather than automatic invoice or purchase posting', async () => {
  const page = await read('app/documents/page.tsx');
  assert.match(page, /Confirm checked details/);
  assert.match(page, /Reject document/);
  assert.match(page, /No business transaction was created/);
  assert.match(page, /Check the original/);
  assert.match(page, /Download original/);
  assert.doesNotMatch(page, /postPurchaseReceipt\(|postExpense\(|createPurchaseOrder\(/);
});

test('AI assistant uses authenticated server-side policy routing and keeps tenant data out of prompts', async () => {
  const page = await read('app/ai-assistant/page.tsx');
  const client = await read('lib/ai-assistant-api.ts');
  assert.match(page, /Your LEXA business assistant/);
  assert.match(page, /Private to your signed-in workspace/);
  assert.match(page, /Your business question/);
  assert.match(page, /MarkdownAnswer/);
  assert.doesNotMatch(page, /assistant-provider|Assistant service/);
  assert.match(page, /askLexaAssistant/);
  assert.match(client, /\/api\/lexa\/api\/v1\/ai\/assistant/);
  assert.match(client, /Authorization: `Bearer \$\{token\}`/);
  assert.match(client, /include_business_summary: false/);
  assert.doesNotMatch(client, /tenant_id|user_id|workspace_id/);
  assert.doesNotMatch(`${page}\n${client}`, /api\.openai\.com|generativelanguage\.googleapis\.com|api\.groq\.com|NEXT_PUBLIC_[A-Z0-9_]*KEY/i);
  assert.doesNotMatch(page, /fetch\s*\(|The assistant isn’t available right now|This page will not generate or pretend to generate an answer/);
});

test('document review API uses no browser-side secrets or model endpoints', async () => {
  const api = await read('lib/document-intelligence-api.ts');
  assert.doesNotMatch(api, /NEXT_PUBLIC_.*KEY|api\.openai\.com|generativelanguage\.googleapis\.com|api\.groq\.com/);
});

test('daily brief page displays rule-based findings and keeps data-quality separate', async () => {
  const page = await read('app/daily-brief/page.tsx');
  const api = await read('lib/daily-brief-api.ts');
  assert.match(page, /Your business, at a glance/);
  assert.match(page, /What to check first/);
  assert.match(page, /Information to check or update/);
  assert.match(page, /Missing information is never treated as zero/);
  assert.match(api, /\/api\/v1\/intelligence\/daily-brief/);
  assert.match(api, /Authorization: `Bearer \$\{token\}`/);
  assert.match(api, /business_writes_performed/);
});

test('daily brief is reachable in navigation and search', () => {
  assert.ok(applicationRoutes.includes('/daily-brief'));
  assert.ok(primaryNavigation.some(([href]) => href === '/daily-brief'));
  assert.equal(resolveBusinessSearchDestination('show me the daily brief'), '/daily-brief?q=show%20me%20the%20daily%20brief');
});
