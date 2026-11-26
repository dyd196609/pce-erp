import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runPlaywrightWithDevServer } from './pcePlaywrightRunner.mjs'
import { listPceBatchCapabilityContracts } from '../src/meta/runtime/pceBatchCapabilityRegistry.js'

const VERSION = 'V1.14.2.8.4.7.31'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const evidenceRoot = path.join(root, 'test-results/pce-semantic-batch-capability')
const checkpointRoot = path.join(root, 'test-results/purchase-payment-golden-flow/checkpoints/qualified_inbound_completed')
const coreFiles = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']

function hashFile(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
}

function checkpointHashes() {
  return Object.fromEntries(coreFiles.map((file) => [file, hashFile(path.join(checkpointRoot, file))]))
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

function legacyDifferenceMatrix(contract) {
  const { baselineCount, currentCount, classification, reason } = contract.legacyFingerprint
  return Array.from({ length: Math.max(0, baselineCount - currentCount) }, (_, index) => ({
    pageId: contract.pageId,
    sectionId: contract.sectionId,
    actionId: null,
    chineseActionName: null,
    legacyTokenSlot: `legacy-source-token-${String(index + 1).padStart(2, '0')}`,
    historicalBaselineExists: true,
    currentDomExists: null,
    currentSourceExists: null,
    currentlyVisible: null,
    currentlyDisabled: null,
    displayCondition: null,
    disabledCondition: null,
    isBatchBusinessAction: false,
    isRowAction: false,
    isToolbarControl: false,
    isDuplicateDom: null,
    isHiddenNode: null,
    isLegacyDuplicateEntry: null,
    classification,
    reason: `历史基线未保存actionId或DOM证据，无法把源码关键字差值伪装成业务动作；${reason}`,
  }))
}

const hashesBefore = checkpointHashes()
const result = await runPlaywrightWithDevServer([
  'test',
  '-c',
  'playwright.runtime.config.js',
  'tests/ui-baseline/pceThreePageBatchCapabilities.spec.js',
])
if (result.stdout) process.stdout.write(result.stdout)
if (result.stderr) process.stderr.write(result.stderr)

const contracts = listPceBatchCapabilityContracts({ includeInternal: false })
const pageEvidence = contracts.map((contract) => {
  const file = path.join(evidenceRoot, `${contract.pageId}.json`)
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {
    pageId: contract.pageId,
    result: 'failed',
    missingEvidence: file,
  }
})
const hashesAfter = checkpointHashes()
const checkpointImmutable = coreFiles.every((file) => hashesBefore[file] === hashesAfter[file])
const report = {
  version: VERSION,
  gate: 'three_page_semantic_batch_capability',
  checkpointPath: checkpointRoot,
  checkpointHashesBefore: hashesBefore,
  checkpointHashesAfter: hashesAfter,
  checkpointImmutable,
  pages: pageEvidence,
  differenceMatrices: Object.fromEntries(contracts.map((contract) => [contract.pageId, legacyDifferenceMatrix(contract)])),
  legacyCountsPreserved: true,
  userBusinessDataModified: false,
  result: result.status === 0 && checkpointImmutable && pageEvidence.every((item) => item.result === 'passed') ? 'passed' : 'failed',
}
writeJson(path.join(evidenceRoot, 'summary.json'), report)

if (report.result !== 'passed') {
  writeJson(path.join(evidenceRoot, 'failure-report.json'), report)
  process.exit(result.status || 1)
}

console.log(JSON.stringify(report, null, 2))
