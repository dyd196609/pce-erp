import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/ui-baseline', testMatch: 'enterprisePageAcceptanceRunnerV11428422.spec.js', workers: 1, fullyParallel: false, retries: 0,
  timeout: 120_000, expect: { timeout: 20_000 },
  use: { baseURL: 'http://localhost:5173', browserName: 'chromium', channel: 'chrome', viewport: { width: 1600, height: 1000 }, trace: 'on', screenshot: 'on' },
  webServer: { command: 'npm run dev:frontend-only', url: 'http://localhost:5173', reuseExistingServer: true, timeout: 120_000 },
  outputDir: 'test-results/page-acceptance-runner-v11428422/playwright-artifacts',
  reporter: [['list'], ['json', { outputFile: 'test-results/page-acceptance-runner-v11428422/playwright-report.json' }]],
})
