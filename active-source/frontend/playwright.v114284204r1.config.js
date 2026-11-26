import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/ui-baseline',
  testMatch: 'scmCanaryScenarioMappingV114284204R1.spec.js',
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  use: { baseURL: 'http://localhost:5173', browserName: 'chromium', channel: 'chrome', viewport: { width: 1600, height: 1000 }, trace: 'on', screenshot: 'on' },
  webServer: { command: 'npm run dev:frontend-only', url: 'http://localhost:5173', reuseExistingServer: true, timeout: 120_000 },
  outputDir: 'test-results/scm-canary-scenario-mapping-v114284204-r1/playwright-artifacts',
  reporter: [['list'], ['json', { outputFile: 'test-results/scm-canary-scenario-mapping-v114284204-r1/playwright-report.json' }]],
})
