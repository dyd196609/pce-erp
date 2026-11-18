import { runPlaywrightWithDevServer } from './pcePlaywrightRunner.mjs'

const VERSION = 'V1.14.2.8.4.7.9'
const result = await runPlaywrightWithDevServer([
  'test',
  '-c',
  'playwright.runtime.config.js',
  'tests/ui-baseline/pceAdvancedFilterToggleRuntime.spec.js',
])

if (result.stdout) process.stdout.write(result.stdout)
if (result.stderr) process.stderr.write(result.stderr)
if (result.error || result.status !== 0) {
  console.error(`${VERSION} advanced-filter toggle runtime gate failed.`)
  if (result.error) console.error(result.error.message)
  process.exit(result.status || 1)
}
console.log(`${VERSION} advanced-filter toggle runtime gate passed.`)
