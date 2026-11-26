import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/ui-baseline',
  testMatch: 'pceEnterpriseListRuntimeV612.spec.js',
  outputDir: './test-results/pce-enterprise-list-runtime-v1/playwright-artifacts',
  reporter: [
    ['line'],
    ['json', {
      outputFile: './test-results/pce-enterprise-list-runtime-v1/playwright-report.json',
    }],
  ],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
    channel: 'chrome',
    viewport: { width: 1440, height: 900 },
    permissions: ['clipboard-read', 'clipboard-write'],
    trace: 'on',
    screenshot: 'on',
  },
})
