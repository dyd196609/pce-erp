import path from 'node:path'
import { frontendRoot, spawnCaptured, warmViteResources, withPceDevServer } from './pcePlaywrightRunner.mjs'
import { createCanonicalRunOutput } from './pceCanonicalEvidence.mjs'

const VERSION = 'V1.14.2.8.4.6'

const result = await withPceDevServer(async ({ childEnv, devServerUrl, registerOwnedBrowser }) => {
  const outputRoot = createCanonicalRunOutput(childEnv.PLAYWRIGHT_OUTPUT_DIR)
  process.stdout.write(`PCE_CANONICAL_OUTPUT ${JSON.stringify({
    runId: childEnv.PCE_PLAYWRIGHT_RUN_ID,
    outputRoot,
    evidence: path.join(outputRoot, 'results'),
    htmlReport: path.join(outputRoot, 'html'),
  })}\n`)
  const warmup = await warmViteResources(devServerUrl)
  process.stdout.write(`PCE_PLAYWRIGHT_RESOURCE_READY ${JSON.stringify(warmup)}\n`)
  return spawnCaptured(process.execPath, [
    path.join(frontendRoot, 'node_modules', '@playwright', 'test', 'cli.js'),
    'test', '-c', 'playwright.canonical.config.js',
    'tests/ui-baseline/pceCanonicalNames.spec.js',
  ], {
    cwd: frontendRoot,
    windowsHide: true,
    env: { ...childEnv, PCE_BASE_URL: devServerUrl, PCE_CANONICAL_OUTPUT_DIR: outputRoot },
  }, registerOwnedBrowser)
})

if (result.stdout) process.stdout.write(result.stdout)
if (result.stderr) process.stderr.write(result.stderr)

if (result.error || result.status !== 0) {
  console.error(`${VERSION} canonical name gate failed.`)
  if (result.error) console.error(result.error.message)
  process.exit(result.status || 1)
}

console.log(`${VERSION} canonical name gate passed.`)
process.exit(0)
