import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './scripts',
  testMatch: 'singleFormalFlow.spec.js',
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: 'http://127.0.0.1:5174',
    browserName: 'chromium',
    channel: 'chrome',
    viewport: { width: 1600, height: 1000 },
    trace: 'on',
    screenshot: 'only-on-failure',
  },
  outputDir: 'test-results/single-formal-flow/playwright-artifacts',
  reporter: [
    ['list'],
    ['json', { outputFile: 'test-results/single-formal-flow/playwright-report.json' }],
  ],
})
