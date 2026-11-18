import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/ui-baseline',
  testMatch: 'bankSendSimulationV64.spec.js',
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: 'http://localhost:5173',
    browserName: 'chromium',
    channel: 'chrome',
    viewport: { width: 1440, height: 900 },
    trace: 'on',
    screenshot: 'on',
  },
  outputDir: 'test-results/bank-send-simulation-v64/playwright-artifacts',
  reporter: [
    ['list'],
    ['json', { outputFile: 'test-results/bank-send-simulation-v64/playwright-report.json' }],
  ],
})
