import fs from 'node:fs'
import path from 'node:path'
import { runPlaywrightWithDevServer, frontendRoot } from './pcePlaywrightRunner.mjs'

const VERSION = 'V1.14.2.8.4.4'
const result = await runPlaywrightWithDevServer([
  'test',
  '-c',
  'playwright.runtime.config.js',
  'tests/ui-baseline/pceAllBusinessOperationColumns.spec.js',
])

if (result.stdout) process.stdout.write(result.stdout)
if (result.stderr) process.stderr.write(result.stderr)

const manifestPath = path.join(frontendRoot, 'test-results/pce-operation-columns/operation-column-manifest.json')
if (!fs.existsSync(manifestPath)) {
  console.error(`${VERSION} all-business operation-column manifest is missing.`)
  process.exit(1)
}
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
console.log(JSON.stringify({
  version: manifest.version,
  discoveredBusinessPageCount: manifest.discoveredBusinessPageCount,
  discoveredBusinessTableCount: manifest.discoveredBusinessTableCount,
  discoveredOperationRequiredTableCount: manifest.discoveredOperationRequiredTableCount,
  existingOperationColumnCount: manifest.existingOperationColumnCount,
  runtimeTestedOperationTableCount: manifest.runtimeTestedOperationTableCount,
  runtimePassedOperationTableCount: manifest.runtimePassedOperationTableCount,
  missingOperationColumnCount: manifest.missingOperationColumnCount,
  operationHeaderOnlyCount: manifest.operationHeaderOnlyCount,
  operationColumnNotFixedCount: manifest.operationColumnNotFixedCount,
  floatingOperationColumnCount: manifest.floatingOperationColumnCount,
  jitterOperationColumnCount: manifest.jitterOperationColumnCount,
  notAtRightEdgeOperationColumnCount: manifest.notAtRightEdgeOperationColumnCount,
  coveredOperationColumnCount: manifest.coveredOperationColumnCount,
  coversBusinessColumnCount: manifest.coversBusinessColumnCount,
  transparentOperationColumnCount: manifest.transparentOperationColumnCount,
  clippedOperationButtonCount: manifest.clippedOperationButtonCount,
  unclickableOperationButtonCount: manifest.unclickableOperationButtonCount,
  wrongRecordOperationButtonCount: manifest.wrongRecordOperationButtonCount,
  unstableWidthOperationColumnCount: manifest.unstableWidthOperationColumnCount,
  untestedOperationTableCount: manifest.untestedOperationTableCount,
  overallStatus: manifest.overallStatus,
}, null, 2))

if (result.error || result.status !== 0 || manifest.overallStatus !== 'passed') {
  console.error(`${VERSION} all-business operation-column gate failed.`)
  if (result.error) console.error(result.error.message)
  process.exit(result.status || 1)
}

console.log(`${VERSION} all-business operation-column gate passed.`)
