import { defineConfig } from '@playwright/test';

const baseURL = process.env.LEXA_BROWSER_BASE_URL || 'http://127.0.0.1:3000';
const storageState = process.env.LEXA_PHASE2_STORAGE_STATE
  || process.env.LEXA_PHASE8_STORAGE_STATE
  || process.env.LEXA_PHASE7_STORAGE_STATE
  || process.env.LEXA_PHASE7_REVERSAL_STORAGE_STATE
  || process.env.LEXA_PHASE7_APPROVAL_STORAGE_STATE
  || process.env.LEXA_PHASE6_STORAGE_STATE
  || process.env.LEXA_PHASE5_STORAGE_STATE
  || process.env.LEXA_PHASE4_STORAGE_STATE
  || { cookies: [], origins: [] };
const stagingWritesEnabled = [
  'LEXA_PHASE2_ALLOW_STAGING_WRITES',
  'LEXA_PHASE5_ALLOW_STAGING_WRITES',
  'LEXA_PHASE6_ALLOW_STAGING_WRITES',
  'LEXA_PHASE7_ALLOW_STAGING_WRITES',
  'LEXA_PHASE7_REVERSAL_ALLOW_STAGING_WRITES',
  'LEXA_PHASE7_APPROVAL_ALLOW_STAGING_WRITES',
  'LEXA_PHASE7_ALLOCATION_ALLOW_STAGING_WRITES',
  'LEXA_PHASE8_ALLOW_STAGING_WRITES',
].some((key) => process.env[key] === '1');

const phase5Through8AcceptancePattern = /phase(5-sales|6-inventory|7-purchasing|7-authorization|8-reports)-acceptance\.spec\.ts$/;
const phase2TransactionAcceptancePattern = /phase2-transaction-acceptance\.spec\.ts$/;
const phase7ReversalAcceptancePattern = /phase7-reversal-acceptance\.spec\.ts$/;
const phase7ApprovalAcceptancePattern = /phase7-approval-limits-acceptance\.spec\.ts$/;
const phase7AllocationAcceptancePattern = /phase7-partial-allocations-acceptance\.spec\.ts$/;

export default defineConfig({
  testDir: './e2e',
  // Write-enabled reversal tests are a separate explicit matcher and remain
  // fail-closed behind their own staging host, role and disposable-fixture checks.
  testMatch: [phase5Through8AcceptancePattern, phase2TransactionAcceptancePattern, phase7ReversalAcceptancePattern, phase7ApprovalAcceptancePattern, phase7AllocationAcceptancePattern],
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: false,
  workers: 1,
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
