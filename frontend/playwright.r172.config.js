import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/auth',
  testMatch: 'loginManualInteractionR172.spec.js',
  workers: 1,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: 'http://localhost:5173',
    browserName: 'chromium',
    channel: 'chrome',
    viewport: { width: 1600, height: 1000 },
    trace: 'on',
    screenshot: 'only-on-failure',
  },
  outputDir: 'test-results/login-manual-interaction-r17-2/playwright-artifacts',
  reporter: [
    ['list'],
    ['json', { outputFile: 'test-results/login-manual-interaction-r17-2/playwright-report.json' }],
  ],
})
