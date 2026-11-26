import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const VERSION = 'V1.14.2.8.4.4'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const manifestPath = path.join(root, 'test-results/pce-operation-columns/operation-column-manifest.json')

function listFiles(dir, predicate) {
  if (!fs.existsSync(dir)) return []
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(dir, entry.name)
    return entry.isDirectory() ? listFiles(target, predicate) : predicate(target) ? [target] : []
  })
}

function sourceFingerprint() {
  const files = [
    ...listFiles(path.join(root, 'src/meta/pages'), (file) => file.endsWith('.vue')),
    path.join(root, 'src/meta/components/BusinessTableScrollContainer.vue'),
    path.join(root, 'src/meta/runtime/pceTableFixedColumnContract.js'),
    path.join(root, 'src/router/index.js'),
    path.join(root, 'src/styles/appExperience.css'),
  ].filter((file) => fs.existsSync(file)).sort()
  const hash = crypto.createHash('sha256')
  for (const file of files) {
    hash.update(path.relative(root, file).replaceAll('\\', '/'))
    hash.update(fs.readFileSync(file))
  }
  return hash.digest('hex')
}

if (!fs.existsSync(manifestPath)) {
  console.error(`${VERSION} operation-column manifest missing; run verify:pce-all-business-operation-columns.`)
  process.exit(1)
}

const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
const required = (manifest.tables || []).filter((item) => item.operationRequired)
const failures = []
if (manifest.version !== VERSION) failures.push('manifest_version_mismatch')
if (manifest.sourceFingerprint !== sourceFingerprint()) failures.push('operation_source_fingerprint_mismatch')
if (manifest.overallStatus !== 'passed') failures.push('manifest_overall_failed')
if (manifest.discoveredOperationRequiredTableCount !== required.length) failures.push('required_count_mismatch')
if (manifest.runtimeTestedOperationTableCount !== required.length) failures.push('tested_count_mismatch')
if (manifest.runtimePassedOperationTableCount !== required.length) failures.push('passed_count_mismatch')

for (const item of required) {
  if (item.overallStatus !== 'passed') failures.push(`${item.pageId}/${item.tableId}:failed`)
  const positionPercents = new Set((item.positions || []).map((position) => position.percent))
  if (![0, 50, 100].every((percent) => positionPercents.has(percent))) failures.push(`${item.pageId}/${item.tableId}:position_evidence_missing`)
  for (const screenshot of Object.values(item.screenshotPaths || {})) {
    if (!fs.existsSync(path.join(root, screenshot))) failures.push(`${item.pageId}/${item.tableId}:screenshot_missing`)
  }
}

console.log(JSON.stringify({
  version: VERSION,
  sourceFingerprintMatched: manifest.sourceFingerprint === sourceFingerprint(),
  discoveredBusinessPageCount: manifest.discoveredBusinessPageCount,
  discoveredBusinessTableCount: manifest.discoveredBusinessTableCount,
  discoveredOperationRequiredTableCount: manifest.discoveredOperationRequiredTableCount,
  runtimeTestedOperationTableCount: manifest.runtimeTestedOperationTableCount,
  runtimePassedOperationTableCount: manifest.runtimePassedOperationTableCount,
  failureCount: failures.length,
  failures,
}, null, 2))

if (failures.length) process.exit(1)
console.log(`${VERSION} all-business operation-column evidence gate passed.`)
