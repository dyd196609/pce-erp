import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/ui-baseline',
  testMatch: 'processCenterGovernanceV841.spec.js',
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 12_000 },
  use: {
    baseURL: 'http://127.0.0.1:5173',
    browserName: 'chromium',
    channel: 'chrome',
    viewport: { width: 1600, height: 1000 },
    trace: 'on',
    screenshot: 'on',
  },
  outputDir: 'test-results/process-center-governance-v841/playwright-artifacts',
  reporter: [
    ['list'],
    ['json', { outputFile: 'test-results/process-center-governance-v841/playwright-report.json' }],
  ],
})
