import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { pceWideTableContracts } from '../src/meta/runtime/pceUiBaseline.js'

const VERSION = 'V1.14.2.8.4.3'
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const evidenceRoot = path.join(root, 'test-results/pce-fixed-columns')
const failures = []

for (const contract of pceWideTableContracts) {
  const file = path.join(evidenceRoot, `${contract.tableId}.json`)
  if (!fs.existsSync(file)) {
    failures.push({ tableId: contract.tableId, reason: 'missing evidence json' })
    continue
  }
  const evidence = JSON.parse(fs.readFileSync(file, 'utf8'))
  const screenshotPaths = Object.values(evidence.screenshotPaths || {})
  const missingScreenshots = screenshotPaths.filter((item) => !fs.existsSync(item))
  if (evidence.overallStatus !== 'passed') failures.push({ tableId: contract.tableId, reason: 'overallStatus not passed', failureItems: evidence.failureItems })
  if (!evidence.selectionColumnPassed) failures.push({ tableId: contract.tableId, reason: 'selection column failed' })
  if (!evidence.indexColumnPassed) failures.push({ tableId: contract.tableId, reason: 'index column failed' })
  if (!evidence.primaryNoColumnPassed) failures.push({ tableId: contract.tableId, reason: 'primary number column failed' })
  if (!evidence.operationColumnPassed) failures.push({ tableId: contract.tableId, reason: 'operation column failed' })
  if (missingScreenshots.length) failures.push({ tableId: contract.tableId, reason: 'missing screenshots', missingScreenshots })
}

const evidenceFiles = fs.existsSync(evidenceRoot)
  ? fs.readdirSync(evidenceRoot).filter((item) => item.endsWith('.json'))
  : []

const summary = {
  version: VERSION,
  discoveredBusinessTableCount: pceWideTableContracts.length,
  fixedColumnEvidenceCount: evidenceFiles.length,
  selectionColumnPassedCount: pceWideTableContracts.length - failures.filter((item) => item.reason === 'selection column failed').length,
  indexColumnPassedCount: pceWideTableContracts.length - failures.filter((item) => item.reason === 'index column failed').length,
  primaryNoColumnPassedCount: pceWideTableContracts.length - failures.filter((item) => item.reason === 'primary number column failed').length,
  operationColumnPassedCount: pceWideTableContracts.length - failures.filter((item) => item.reason === 'operation column failed').length,
  failureCount: failures.length,
  failures,
}

console.log(JSON.stringify(summary, null, 2))

if (evidenceFiles.length !== pceWideTableContracts.length || failures.length) {
  console.error(`${VERSION} fixed column evidence gate failed.`)
  process.exit(1)
}

console.log(`${VERSION} fixed column evidence gate passed.`)
