export default {
  testDir: './tests',
  outputDir: './test-results/playwright-default-output',
  timeout: 30000,
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
  },
  webServer: {
    command: 'npm run dev:frontend-only',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 120000,
  },
}
