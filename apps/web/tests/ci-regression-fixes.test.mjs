import fs from 'node:fs';
import assert from 'node:assert/strict';

const web = new URL('../', import.meta.url);
const compliance = fs.readFileSync(new URL('app/compliance/page.tsx', web), 'utf8');
const assistantTest = fs.readFileSync(new URL('../api/tests/test_ai_assistant.py', web), 'utf8');
const intelligence = fs.readFileSync(new URL('../api/app/intelligence/routes.py', web), 'utf8');

assert.match(compliance, /No tax rates are saved yet/);
assert.match(compliance, /Configure a default tax rule/);
assert.match(compliance, /No official fiscal documents have been recorded yet/);
assert.match(compliance, /real URA-approved connector/i);
assert.match(compliance, /Tax rate end date cannot be before its start date\./i);
assert.match(compliance, /Tax rule end date cannot be before its start date\./i);
assert.match(assistantTest, /item\["model"\] == "gpt-5-mini"/);
assert.match(intelligence, /"business_tool_execution":\s*\{/);
assert.match(intelligence, /"automatic_business_writes": False/);
assert.match(intelligence, /"execution_available": False/);
console.log('Known CI contract regression fixes: PASS');
