import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/ui-baseline',
  testMatch: 'pceFilterContractV521.spec.js',
  timeout: 300_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  outputDir: 'test-results/pce-filter-contract-v521/playwright-output',
  reporter: [['line']],
  use: {
    baseURL: process.env.PCE_V521_BASE_URL || 'http://127.0.0.1:5173',
    browserName: 'chromium',
    channel: 'chrome',
    viewport: { width: 1366, height: 768 },
    trace: 'on',
    screenshot: 'only-on-failure',
  },
  projects: [{
    name: 'pce-filter-contract-v521-chrome',
    use: { ...devices['Desktop Chrome'], channel: 'chrome' },
  }],
})
