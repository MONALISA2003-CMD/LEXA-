import { defineConfig } from '@playwright/test';

const baseURL = process.env.LEXA_BROWSER_BASE_URL || 'http://127.0.0.1:3000';
const storageState = process.env.LEXA_PHASE2_STORAGE_STATE
  || process.env.LEXA_PHASE8_STORAGE_STATE
  || process.env.LEXA_PHASE7_STORAGE_STATE
  || process.env.LEXA_PHASE6_STORAGE_STATE
  || process.env.LEXA_PHASE5_STORAGE_STATE
  || process.env.LEXA_PHASE4_STORAGE_STATE
  || { cookies: [], origins: [] };
const stagingWritesEnabled = [
  'LEXA_PHASE2_ALLOW_STAGING_WRITES',
  'LEXA_PHASE5_ALLOW_STAGING_WRITES',
  'LEXA_PHASE6_ALLOW_STAGING_WRITES',
  'LEXA_PHASE7_ALLOW_STAGING_WRITES',
  'LEXA_PHASE8_ALLOW_STAGING_WRITES',
].some((key) => process.env[key] === '1');

const phase5Through8AcceptancePattern = /phase(5-sales|6-inventory|7-purchasing|7-authorization|8-reports)-acceptance\.spec\.ts$/;
const phase2TransactionAcceptancePattern = /phase2-transaction-acceptance\.spec\.ts$/;

export default defineConfig({
  testDir: './e2e',
  // Explicit per-phase patterns make it clear which acceptance suites are matched.
  // Write-enabled suites remain opt-in and fail closed in globalSetup and each spec.
  testMatch: [phase5Through8AcceptancePattern, phase2TransactionAcceptancePattern],
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: false,
  workers: 1,
  // Write-enabled financial/inventory E2E can partially mutate disposable fixtures;
  // auto-retrying such a test can replay a lifecycle, so it is always single-attempt.
  retries: stagingWritesEnabled ? 0 : (process.env.CI ? 1 : 0),
  reporter: 'list',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  outputDir: stagingWritesEnabled ? 'test-results/staging-acceptance' : 'test-results/safe-contracts',
  use: {
    baseURL,
    storageState,
    browserName: 'chromium',
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
});
