import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const css = readFileSync(resolve(webRoot, 'app/globals.css'), 'utf8');
const ui = readFileSync(resolve(webRoot, 'components/ui.tsx'), 'utf8');

 test('shared UI primitives are exported and retain compatible legacy button classes', () => {
  for (const primitive of ['export function Button(', 'export function Badge(', 'export function Skeleton(']) {
    assert.ok(ui.includes(primitive), `missing shared primitive: ${primitive}`);
  }
  for (const legacyClass of ['button-dark', 'button-soft', 'button-light', 'button-danger', 'button-small', 'button-large']) {
    assert.ok(ui.includes(legacyClass), `missing compatible class mapping: ${legacyClass}`);
  }
  assert.match(ui, /disabled=\{Boolean\(disabled \|\| loading\)\}/);
  assert.match(ui, /aria-busy=\{loading \|\| undefined\}/);
});

test('form fields associate helper and validation text with direct input controls', () => {
  assert.match(ui, /const describedBy = \[hintId, errorId\]/);
  assert.match(ui, /"aria-describedby": \[existingDescription, describedBy\]/);
  assert.match(ui, /"aria-invalid": error \? true/);
  assert.match(ui, /id=\{hintId\} className="form-field-hint"/);
  assert.match(ui, /id=\{errorId\} className="form-field-error" role="alert"/);
});

test('confirmation dialog contains focus, blocks Escape while busy and restores previous focus', () => {
  assert.match(ui, /dialogRef\.current\?\.querySelectorAll/);
  assert.match(ui, /event\.key === "Escape"/);
  assert.match(ui, /if \(!busyRef\.current\) onCancelRef\.current\(\)/);
  assert.match(ui, /event\.shiftKey/);
  assert.match(ui, /previouslyFocused\?\.isConnected\) previouslyFocused\.focus\(\)/);
  assert.match(ui, /aria-modal="true"/);
});

test('design tokens style buttons, badges, skeletons, forms and dialogs consistently', () => {
  for (const token of ['--lexa-success', '--lexa-info', '--lexa-warning-soft', '--lexa-danger-soft', '--lexa-control-height', '--lexa-shadow-overlay']) {
    assert.ok(css.includes(token), `missing design token: ${token}`);
  }
  for (const selector of ['.lexa-badge-success', '.lexa-badge-warning', '.lexa-badge-danger', '.lexa-skeleton-text', '.lexa-skeleton-rect', '.lexa-skeleton-circle', '.button:focus-visible', '.form-field-invalid input:focus']) {
    assert.ok(css.includes(selector), `missing shared style: ${selector}`);
  }
  assert.match(css, /@media \(max-width: 600px\)[\s\S]*\.lexa-badge/);
});

test('Phase 2 primitives are adopted by real loading and product-status branches', () => {
  const dashboard = readFileSync(resolve(webRoot, 'app/page.tsx'), 'utf8');
  const products = readFileSync(resolve(webRoot, 'app/products/page.tsx'), 'utf8');
  assert.match(dashboard, /import \{ Skeleton \} from "\.\.\/components\/ui"/);
  assert.match(dashboard, /function LoadingPlaceholder\(/);
  assert.match(dashboard, /<LoadingPlaceholder label="Loading operational exceptions…"/);
  assert.match(dashboard, /<LoadingPlaceholder label="Loading business movement…"/);
  assert.match(products, /import \{ Badge, ResponsiveDataTable \} from "\.\.\/\.\.\/components\/ui"/);
  assert.match(products, /<Badge variant=\{product\.status === "ACTIVE" \? "success" : "neutral"\}>/);
});
