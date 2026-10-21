import { defineConfig } from '@playwright/test';

const baseURL = process.env.LEXA_BROWSER_BASE_URL || 'http://127.0.0.1:3000';
const storageState = process.env.LEXA_PHASE5_STORAGE_STATE
  || process.env.LEXA_PHASE4_STORAGE_STATE
  || { cookies: [], origins: [] };

export default defineConfig({
  testDir: './e2e',
  testMatch: 'phase5-sales-acceptance.spec.ts',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  outputDir: 'test-results/phase5',
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
