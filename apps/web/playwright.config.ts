import { defineConfig } from '@playwright/test';
import { baseUrl } from './e2e/env';

// Live E2E suite against the deployed backend (Render by default, override
// with GARDEN_TEST_BASE_URL). Specs are serial and share one worker: they
// build ONE [E2E] garden, exercise every feature, and tear it down in
// 99-teardown, so order and shared state matter.
export default defineConfig({
  testDir: './e2e',
  // The sync/ specs are the web half of the cross-platform relay; only the
  // orchestrator (scripts/run_e2e.ps1) runs them, with E2E_SYNC=1.
  testIgnore: process.env.E2E_SYNC ? [] : ['**/sync/**'],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  // Render free tier + Neon can be slow; be generous everywhere.
  timeout: 120_000,
  expect: { timeout: 20_000 },
  globalSetup: './e2e/global-setup',
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: baseUrl,
    actionTimeout: 20_000,
    navigationTimeout: 60_000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    storageState: '.playwright/auth-state.json',
  },
});
