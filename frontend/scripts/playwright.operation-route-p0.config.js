export default {
  testDir: '.',
  testMatch: 'operationRouteRecoveryP0.spec.js',
  outputDir: '../test-results/operation-route-recovery-p0-playwright',
  timeout: 30000,
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
    launchOptions: { executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' },
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'npm run dev:frontend-only',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 120000,
  },
}
