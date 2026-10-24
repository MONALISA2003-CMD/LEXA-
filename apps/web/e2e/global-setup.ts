import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const productionHosts = new Set(['lexa-green.vercel.app', 'lexa-n10e.onrender.com']);

type PhaseGuard = {
  name: string; flag: string; baseUrl: string; allowList: string;
  fixtureJson: string; storageState: string; allowedRoles: string[]; requiredFixtureKeys: string[];
};

function guardConfigs(): PhaseGuard[] {
  return [
    {
      name: 'Phase 2 transaction chain', flag: 'LEXA_PHASE2_ALLOW_STAGING_WRITES',
      baseUrl: process.env.LEXA_BROWSER_BASE_URL || '',
      allowList: process.env.LEXA_PHASE2_STAGING_HOSTS || '',
      fixtureJson: process.env.LEXA_PHASE2_ACCEPTANCE_FIXTURE_JSON || '',
      storageState: process.env.LEXA_PHASE2_STORAGE_STATE || '',
      allowedRoles: ['owner', 'administrator'],
      requiredFixtureKeys: ['branch_id', 'location_id', 'customer_party_id', 'variant_id', 'payment_channel_id', 'currency_code', 'business_date', 'unit_price', 'quantity', 'initial_payment', 'expected_total'],
    },
    {
      name: 'Phase 6 inventory', flag: 'LEXA_PHASE6_ALLOW_STAGING_WRITES',
      baseUrl: process.env.LEXA_BROWSER_BASE_URL || '',
      allowList: process.env.LEXA_PHASE6_STAGING_HOSTS || '',
      fixtureJson: process.env.LEXA_PHASE6_ACCEPTANCE_FIXTURE_JSON || '',
      storageState: process.env.LEXA_PHASE6_STORAGE_STATE || '',
      allowedRoles: ['owner', 'administrator', 'manager'],
      requiredFixtureKeys: ['location_id', 'restricted_location_id', 'variant_id'],
    },
    {
      name: 'Phase 7 purchasing', flag: 'LEXA_PHASE7_ALLOW_STAGING_WRITES',
      baseUrl: process.env.LEXA_BROWSER_BASE_URL || '',
      allowList: process.env.LEXA_PHASE7_STAGING_HOSTS || '',
      fixtureJson: process.env.LEXA_PHASE7_ACCEPTANCE_FIXTURE_JSON || '',
      storageState: process.env.LEXA_PHASE7_STORAGE_STATE || process.env.LEXA_PHASE5_STORAGE_STATE || process.env.LEXA_PHASE4_STORAGE_STATE || '',
      allowedRoles: ['owner', 'administrator', 'manager', 'finance'],
      requiredFixtureKeys: ['branch_id', 'location_id', 'variant_id', 'currency_code', 'unit_cost', 'order_quantity', 'receipt_quantity', 'landed_cost_amount', 'restricted_purchase_order_id'],
    },
  ];
}

function failClosed(message: string): never {
  // Do not print fixture contents, cookies, tokens, URLs with credentials or API bodies.
  throw new Error(`LEXA staging-write guard blocked acceptance: ${message}`);
}

export default async function globalSetup(): Promise<void> {
  const enabled = guardConfigs().filter(item => process.env[item.flag] === '1');
  if (enabled.length === 0) return;
  for (const guard of enabled) {
    let target: URL;
    try { target = new URL(guard.baseUrl); }
    catch { failClosed(`${guard.name}: LEXA_BROWSER_BASE_URL must be a valid HTTPS origin.`); }
    if (target.protocol !== 'https:' || target.username || target.password || target.search || target.hash || !['', '/'].includes(target.pathname)) {
      failClosed(`${guard.name}: target must be a plain HTTPS origin without credentials, query, fragment, or path.`);
    }
    const host = target.hostname.toLowerCase();
    const allowed = guard.allowList.split(',').map(v => v.trim().toLowerCase()).filter(Boolean);
    if (productionHosts.has(host)) failClosed(`${guard.name}: known production hosts are forbidden for write-enabled tests.`);
    if (!allowed.includes(host)) failClosed(`${guard.name}: hostname is not in the explicit staging allow-list.`);
    if (!guard.fixtureJson) failClosed(`${guard.name}: disposable fixture JSON is required.`);
    let fixture: Record<string, unknown>;
    try { fixture = JSON.parse(guard.fixtureJson) as Record<string, unknown>; }
    catch { failClosed(`${guard.name}: fixture JSON is invalid.`); }
    if (fixture.environment !== 'staging' || fixture.disposable_scope !== true || fixture.reset_strategy !== 'dispose_test_tenant') {
      failClosed(`${guard.name}: fixture must declare staging, disposable_scope=true and reset_strategy=dispose_test_tenant.`);
    }
    if (typeof fixture.actor_role !== 'string' || !guard.allowedRoles.includes(fixture.actor_role)) {
      failClosed(`${guard.name}: fixture actor_role is not eligible for this acceptance suite.`);
    }
    for (const key of guard.requiredFixtureKeys) {
      if (fixture[key] === undefined || fixture[key] === null || fixture[key] === '') failClosed(`${guard.name}: fixture is missing required field ${key}.`);
    }
    if (!guard.storageState) failClosed(`${guard.name}: separate authenticated QA storage state is required.`);
    const storagePath = resolve(guard.storageState);
    if (!existsSync(storagePath)) failClosed(`${guard.name}: authenticated QA storage-state file is missing.`);
    try {
      const state = JSON.parse(readFileSync(storagePath, 'utf8')) as { cookies?: unknown; origins?: unknown };
      if (!Array.isArray(state.cookies) || !Array.isArray(state.origins)) failClosed(`${guard.name}: storage state is invalid.`);
    } catch { failClosed(`${guard.name}: storage state is invalid.`); }
    let response: Response;
    try { response = await fetch(`${target.origin}/api/lexa/ready`, { redirect: 'error', signal: AbortSignal.timeout(10_000) }); }
    catch { failClosed(`${guard.name}: readiness probe failed without following redirects.`); }
    if (response.status !== 200) failClosed(`${guard.name}: readiness endpoint did not return HTTP 200.`);
    let readiness: { status?: string; environment?: string; dependencies?: { database?: string; cache?: string } };
    try { readiness = await response.json() as typeof readiness; }
    catch { failClosed(`${guard.name}: readiness response was not valid JSON.`); }
    if (readiness.status !== 'ready' || !['staging', 'test'].includes(String(readiness.environment || '').toLowerCase())) {
      failClosed(`${guard.name}: target did not identify itself as a ready staging/test environment.`);
    }
    if (readiness.dependencies?.database !== 'ok' || readiness.dependencies?.cache !== 'ok') {
      failClosed(`${guard.name}: database and cache must both be healthy before test writes.`);
    }
  }
}
