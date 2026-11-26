import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/ui-baseline',
  testMatch: 'bankSendExecutionGateV60.spec.js',
  workers: 1,
  reporter: [['list'], ['json', {
    outputFile: 'test-results/bank-send-execution-gate-v60/playwright-report.json',
  }]],
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
    channel: 'chrome',
    trace: 'on',
    screenshot: 'on',
    permissions: ['clipboard-read', 'clipboard-write'],
    viewport: { width: 1440, height: 1000 },
  },
  outputDir: 'test-results/bank-send-execution-gate-v60/playwright-artifacts',
})
