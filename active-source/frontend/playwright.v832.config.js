import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/ui-baseline',
  testMatch: 'businessProcessCenterV832.spec.js',
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: 'http://127.0.0.1:5173',
    browserName: 'chromium',
    channel: 'chrome',
    viewport: { width: 1600, height: 1000 },
    trace: 'on',
    screenshot: 'on',
  },
  outputDir: 'test-results/business-process-center-v832/playwright-artifacts',
  reporter: [
    ['list'],
    ['json', { outputFile: 'test-results/business-process-center-v832/playwright-report.json' }],
  ],
})

