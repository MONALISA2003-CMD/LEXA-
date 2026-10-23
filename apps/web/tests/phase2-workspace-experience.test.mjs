import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  applicationRoutes,
  primaryNavigation,
  quickNavigation,
  secondaryNavigation,
  workspaceSearchSuggestions,
  isRouteActive,
  resolveBusinessSearchDestination,
} from '../lib/navigation.mjs';

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => fs.readFileSync(path.join(webRoot, p), 'utf8');
const pagePath = (route) => route === '/' ? 'app/page.tsx' : `app${route}/page.tsx`;

function routeFromHref(href) {
  if (!href.startsWith('/')) return null;
  return href.split(/[?#]/, 1)[0] || '/';
}

test('every canonical navigation, mobile shortcut, and search destination has a real page', () => {
  const declaredRoutes = new Set(applicationRoutes);
  for (const route of declaredRoutes) assert.ok(fs.existsSync(path.join(webRoot, pagePath(route))), `missing page for ${route}`);
  for (const [href] of [...primaryNavigation, ...quickNavigation, ...secondaryNavigation]) {
    assert.ok(declaredRoutes.has(href), `navigation points at undeclared route ${href}`);
    assert.ok(fs.existsSync(path.join(webRoot, pagePath(href))), `navigation points at missing page ${href}`);
  }
  for (const [label, href] of workspaceSearchSuggestions) {
    assert.ok(declaredRoutes.has(href), `search suggestion ${label} points at undeclared route ${href}`);
    assert.ok(fs.existsSync(path.join(webRoot, pagePath(href))), `search suggestion ${label} points at missing page ${href}`);
  }
});

test('route active checks respect segment boundaries and root semantics', () => {
  assert.equal(isRouteActive('/', '/'), true);
  assert.equal(isRouteActive('/reports', '/'), false);
  assert.equal(isRouteActive('/sales', '/sales'), true);
  assert.equal(isRouteActive('/sales/history', '/sales'), true);
  assert.equal(isRouteActive('/sales-history', '/sales'), false);
});

test('natural-language search routes to the expected business modules', () => {
  assert.equal(resolveBusinessSearchDestination('URA fiscal receipt'), '/compliance?q=URA%20fiscal%20receipt');
  assert.equal(resolveBusinessSearchDestination('low stock at warehouse'), '/inventory?q=low%20stock%20at%20warehouse');
  assert.equal(resolveBusinessSearchDestination('team roles and access'), '/administration/members?q=team%20roles%20and%20access');
  assert.equal(resolveBusinessSearchDestination('forecast sales'), '/intelligence?q=forecast%20sales');
  assert.equal(resolveBusinessSearchDestination('point of sale closing'), '/commerce?q=point%20of%20sale%20closing');
  assert.equal(resolveBusinessSearchDestination('a custom report query'), '/reports?q=a%20custom%20report%20query');
});

test('internal JSX hrefs resolve to known routes and remain client-side links', () => {
  const files = [
    ...walk(path.join(webRoot, 'app')).filter((p) => p.endsWith('.tsx')),
    ...walk(path.join(webRoot, 'components')).filter((p) => p.endsWith('.tsx')),
  ];
  const declaredRoutes = new Set(applicationRoutes);
  const found = new Set();
  for (const file of files) {
    const source = fs.readFileSync(file, 'utf8');
    assert.doesNotMatch(source, /<a\s+[^>]*href\s*=\s*(?:"\/|`\/|\{`\/)/, `${path.relative(webRoot, file)} has a raw internal anchor; use Next Link`);
    const expressions = [
      /\bhref\s*=\s*"(\/[^"#]*)"/g,
      /\bhref\s*=\s*'(\/[^'#]*)'/g,
      /\bhref\s*=\s*\{`(\/[^`]*)`\}/g,
      /\bhref\s*=\s*\{\s*"(\/[^"]*)"\s*\}/g,
    ];
    for (const expression of expressions) {
      for (const match of source.matchAll(expression)) {
        const route = routeFromHref(match[1]);
        if (!route || route.startsWith('/api/')) continue;
        found.add(route);
        assert.ok(declaredRoutes.has(route), `${path.relative(webRoot, file)} links to unknown route ${route}`);
      }
    }
  }
  assert.ok(found.size >= 12, `expected broad internal-link coverage, found ${found.size} routes`);
});

test('search palette is accessible and dashboards remain connected to real API data', () => {
  const shell = read('components/app-shell.tsx');
  const dashboard = read('app/page.tsx');
  const charts = read('components/dashboard-charts.tsx');
  const styles = read('app/globals.css');
  assert.match(shell, /role="dialog" aria-modal="true"/);
  assert.match(shell, /searchPanelRef\.current\?\.querySelectorAll/);
  assert.match(shell, /event\.key === "Escape"/);
  assert.match(shell, /workspaceSearchSuggestions\.map/);
  assert.match(shell, /isRouteActive\(pathname, href\)/);
  assert.match(dashboard, /getCommerceDashboard\(\)/);
  assert.match(dashboard, /getAnalyticsOverview\(range\.start, range\.end, currencyCode\)/);
  assert.match(dashboard, /lastUpdatedAt/);
  assert.match(charts, /<Link className="report-record-link" href=\{row\.href\}>/);
  assert.match(styles, /\.command-suggestions button:focus-visible/);
  assert.match(styles, /\.command-kpi-icon/);
  assert.match(styles, /prefers-reduced-motion:\s*reduce/);
});

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const resolved = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(resolved) : [resolved];
  });
}
