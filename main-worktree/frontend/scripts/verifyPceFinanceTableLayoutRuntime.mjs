import { runPlaywrightWithDevServer } from './pcePlaywrightRunner.mjs'

const VERSION = 'V1.14.2.8.4.3'

const result = await runPlaywrightWithDevServer([
  'test',
  '-c',
  'playwright.runtime.config.js',
  'tests/ui-baseline/pceFinanceTableLayoutFix.spec.js',
])

if (result.stdout) process.stdout.write(result.stdout)
if (result.stderr) process.stderr.write(result.stderr)

if (result.error || result.status !== 0) {
  console.error(`${VERSION} finance table layout runtime gate failed.`)
  if (result.error) console.error(result.error.message)
  process.exit(result.status || 1)
}

console.log(`${VERSION} finance table layout runtime gate passed.`)
process.exit(0)
