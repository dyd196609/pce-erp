const VERSION = 'V1.14.2.8.4.6'
process.env.PCE_DEV_SERVER_URL = 'http://localhost:5174'
process.env.PCE_BASE_URL = process.env.PCE_DEV_SERVER_URL
const { runPlaywrightWithDevServer } = await import('./pcePlaywrightRunner.mjs')
const result = await runPlaywrightWithDevServer([
  'test',
  '-c',
  'playwright.runtime.config.js',
  'tests/ui-baseline/pceSelectionExportCanonical.spec.js',
])

if (result.stdout) process.stdout.write(result.stdout)
if (result.stderr) process.stderr.write(result.stderr)
if (result.error || result.status !== 0) {
  console.error(`${VERSION} selection/export/canonical browser gate failed.`)
  process.exit(result.status || 1)
}
console.log(`${VERSION} selection/export/canonical browser gate passed.`)
