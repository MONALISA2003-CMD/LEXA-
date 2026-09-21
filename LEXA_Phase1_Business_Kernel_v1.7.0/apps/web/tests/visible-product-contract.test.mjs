import fs from 'node:fs';
import assert from 'node:assert/strict';

const page = fs.readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
const api = fs.readFileSync(new URL('../lib/api.ts', import.meta.url), 'utf8');
const proxy = fs.readFileSync(new URL('../app/api/lexa/[...path]/route.ts', import.meta.url), 'utf8');

assert.match(api, /fetch\(`\/api\/lexa\$\{path\}`/);
assert.match(page, /getProducts/);
assert.match(page, /Sign in to manage your products, variants, SKUs and pricing/);
assert.doesNotMatch(page, /PREVIEW-SKU/);
assert.doesNotMatch(page, /BUILD PREVIEW/);
assert.match(proxy, /LEXA_API_URL \|\| process\.env\.NEXT_PUBLIC_API_URL/);
assert.match(proxy, /DEFAULT_API_ORIGIN/);
assert.match(proxy, /authorization/);
console.log('visible product contract: PASS');

assert.match(page, /function CatalogWorkspace\(p: CatalogProps\)/);
assert.doesNotMatch(page, /LEXA_SCHEMA_NOT_READY|WORKSPACE_DATABASE_FAILURE|WORKSPACE_REGISTRATION_FAILURE|request id|request-id|transactional database/i);
assert.doesNotMatch(page, /Database:|LEXA services online|Connection unavailable|Checking business services/);
assert.match(page, /removeItem\("lexa_workspace_id"\)/);
assert.doesNotMatch(page, /align-items: ?end/);
console.log('frontend hardening contract: PASS');
