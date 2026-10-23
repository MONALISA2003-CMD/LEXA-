import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '..');
const pkg = JSON.parse(readFileSync(path.join(web, 'package.json'), 'utf8'));
const lock = JSON.parse(readFileSync(path.join(web, 'package-lock.json'), 'utf8'));
const spec = readFileSync(path.join(web, 'e2e', 'phase5-sales-acceptance.spec.ts'), 'utf8');
const config = readFileSync(path.join(web, 'playwright.config.ts'), 'utf8');

test('Phase 5 authenticated acceptance has a pinned Playwright runner and lockfile', () => {
  assert.equal(pkg.devDependencies['@playwright/test'], '1.64.1');
  assert.equal(lock.packages['node_modules/@playwright/test'].version, '1.64.1');
  assert.equal(lock.packages['node_modules/playwright'].version, '1.64.1');
  assert.equal(lock.packages['node_modules/playwright-core'].version, '1.64.1');
  assert.match(pkg.scripts['test:e2e:phase5'], /playwright test/);
  assert.match(config, /phase\(5-sales\|6-inventory\|7-purchasing\|7-authorization\|8-reports\)-acceptance/);
  assert.match(config, /LEXA_PHASE7_STORAGE_STATE/);
});

test('Phase 5 browser writes fail closed without explicit staging safeguards', () => {
  assert.match(spec, /LEXA_PHASE5_ALLOW_STAGING_WRITES/);
  assert.match(spec, /fixture\?\.environment === 'staging'/);
  assert.match(spec, /stagingHosts\.includes\(baseHost\)/);
  assert.match(spec, /LEXA_PHASE5_STORAGE_STATE/);
  assert.match(spec, /test\.skip\(!optedIn/);
});
