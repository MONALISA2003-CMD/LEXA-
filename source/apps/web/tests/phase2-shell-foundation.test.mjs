import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const css = readFileSync(resolve(webRoot, 'app/globals.css'), 'utf8');
const shell = readFileSync(resolve(webRoot, 'components/app-shell.tsx'), 'utf8');

test('Phase 2 shell tokens are defined and used by the existing shell', () => {
  for (const token of ['--lexa-brand-900', '--lexa-brand-800', '--lexa-accent', '--lexa-canvas', '--lexa-border', '--lexa-focus-ring']) {
    assert.match(css, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
  assert.match(css, /\.app-sidebar\s*\{\s*background:\s*var\(--lexa-brand-900\)/);
  assert.match(css, /\.app-nav-item\.active\s*\{[^}]*var\(--lexa-brand-800\)/s);
});

test('shell retains real session, readiness, logout and business search integration', () => {
  for (const contract of ['restoreSession()', 'getReadiness()', 'logout()', 'router.push(destination)', 'router.replace("/login")']) {
    assert.ok(shell.includes(contract), `missing existing shell contract: ${contract}`);
  }
});

test('responsive and accessibility foundations are present', () => {
  assert.match(css, /@media\s*\(max-width:\s*800px\)/);
  assert.match(css, /@media\s*\(max-width:\s*380px\)/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /\.app-nav-item:focus-visible/);
});
