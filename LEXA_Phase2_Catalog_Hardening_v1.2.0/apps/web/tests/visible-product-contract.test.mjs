import fs from 'node:fs';
import assert from 'node:assert/strict';

const page = fs.readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
const api = fs.readFileSync(new URL('../lib/api.ts', import.meta.url), 'utf8');
const proxy = fs.readFileSync(new URL('../app/api/lexa/[...path]/route.ts', import.meta.url), 'utf8');

assert.match(api, /fetch\(`\/api\/lexa\$\{path\}`/);
assert.match(page, /getProducts/);
assert.match(page, /Sign in to manage the authenticated tenant's products/);
assert.doesNotMatch(page, /PREVIEW-SKU/);
assert.doesNotMatch(page, /BUILD PREVIEW/);
assert.match(proxy, /LEXA_API_URL \|\| process\.env\.NEXT_PUBLIC_API_URL/);
assert.match(proxy, /authorization/);
console.log('visible product contract: PASS');
