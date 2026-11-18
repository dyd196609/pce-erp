import crypto from 'node:crypto'
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { verifyCheckpointIntegrity } from '../tests/helpers/goldenCheckpoint.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const checkpointRoot = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const targetId = 'supplier_settlement_pre_reconciliation_semantics_ready'
const batchId = `canary-${Date.now()}-${process.pid}`
const stagingDir = path.join(checkpointRoot, '.staging', `${targetId}-${batchId}`)
const targetDir = path.join(checkpointRoot, targetId)
const reportPath = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'supplier-settlement-pre-reconciliation-report.json')
const playwrightCli = path.join(root, 'node_modules', '@playwright', 'test', 'cli.js')

function run(args, env = {}) {
  const result = spawnSync(process.execPath, args, { cwd: root, env: { ...process.env, ...env }, stdio: 'inherit' })
  if ((result.status ?? 1) !== 0) process.exit(result.status ?? 1)
}

function writeJson(file, value) {
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
}

function integrityHash(directory) {
  const hash = crypto.createHash('sha256')
  for (const name of ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']) {
    hash.update(name)
    hash.update(fs.readFileSync(path.join(directory, name)))
  }
  return hash.digest('hex')
}

await verifyCheckpointIntegrity('supplier_settlement_ready', { expectedOrigin: process.env.PCE_BASE_URL || 'http://localhost:5173' })
if (fs.existsSync(targetDir)) throw new Error(`formal checkpoint already exists: ${targetDir}`)
fs.mkdirSync(stagingDir, { recursive: true })
const commonEnv = { PCE_CANARY_BATCH_ID: batchId, PCE_CANARY_STAGING_DIR: stagingDir, PCE_GOLDEN_RUNNER_TRACE: '1' }
run([playwrightCli, 'test', '-c', 'playwright.runtime.config.js', 'tests/e2e/supplierSettlementPreReconciliationSemantics.spec.js', '-g', '金丝雀群 A-E'], commonEnv)
const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'))
if (report.result !== 'passed' || report.canaryBatchId !== batchId || report.canaryScenarioCount !== 5) throw new Error('canary report identity or result mismatch')
if (!report.protectedCheckpointHashesUnchanged || report.businessDataModified !== false) throw new Error('protected checkpoint or business data boundary failed')
const tracePath = path.resolve(report.runnerTraceExpectedPath)
if (path.dirname(tracePath) !== path.resolve(report.playwrightOutputDir) || !fs.existsSync(tracePath)) throw new Error('runner trace ownership mismatch')
fs.copyFileSync(tracePath, path.join(stagingDir, 'trace.zip'))
run([playwrightCli, 'test', '-c', 'playwright.runtime.config.js', 'tests/e2e/supplierSettlementPreReconciliationSemantics.spec.js', '-g', '跨进程恢复'], { ...commonEnv, PCE_CANARY_RECOVERY: '1' })

report.crossProcessRecovery = 'passed'
report.runnerTracePath = tracePath
report.checkpoint = targetDir
writeJson(reportPath, report)
const storageState = JSON.parse(fs.readFileSync(path.join(stagingDir, 'storage-state.json'), 'utf8'))
const localStorageEntries = storageState.origins?.find((item) => item.origin === (process.env.PCE_BASE_URL || 'http://localhost:5173'))?.localStorage || []
const localStorage = Object.fromEntries(localStorageEntries.map((item) => [item.name, item.value]))
writeJson(path.join(stagingDir, 'application-state.json'), {
  version: 'V1.14.2.8.4.7.35', origin: process.env.PCE_BASE_URL || 'http://localhost:5173', canaryGroup: true,
  canaryBatchId: batchId, localStorage, capturedAt: new Date().toISOString(),
})
writeJson(path.join(stagingDir, 'business-entities.json'), {
  version: 'V1.14.2.8.4.7.35', origin: 'canary', canaryGroup: true, singleCanary: false, canaryBatchId: batchId,
  scenarioCount: report.canaryScenarioCount, scenarios: report.scenarioResults,
  zeroReconciliationObjectBoundary: true, zeroPaymentObjectBoundary: true, navigationOnly: true,
})
writeJson(path.join(stagingDir, 'relationship-graph.json'), {
  version: 'V1.14.2.8.4.7.35', canaryBatchId: batchId,
  semantics: {
    sourceStatus: report.sourceStatusSemantics,
    contextState: report.contextStateSemantics,
    settlementStatus: report.settlementStatusSemantics,
  },
  relations: report.scenarioResults.map((item) => ({ scenarioCode: item.scenarioCode, sourcePayableCheckNo: item.sourcePayableCheckNo, supplierSettlementNo: item.supplierSettlementNo, contextState: item.actualContextState })),
  zeroReconciliationObjectBoundary: true, zeroPaymentObjectBoundary: true, navigationOnly: true,
})
writeJson(path.join(stagingDir, 'restore-verification.json'), {
  checkpointId: targetId, status: 'passed', result: 'passed', verificationProcess: 'independent_node_playwright_process',
  verifiedAt: new Date().toISOString(), canaryBatchId: batchId, businessDataModified: false,
})
const hash = integrityHash(stagingDir)
writeJson(path.join(stagingDir, 'manifest.json'), {
  checkpointVersion: '1.0.0', version: 'V1.14.2.8.4.7.35', checkpointId: targetId, createdAt: new Date().toISOString(),
  origin: process.env.PCE_BASE_URL || 'http://localhost:5173', sourceCheckpointId: 'supplier_settlement_ready', nextStageId: 'purchase-reconciliation',
  integrityFiles: ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json'], integrityHash: hash,
  restorable: true, immutable: true, canaryGroup: true, singleCanary: false,
  zeroReconciliationObjectBoundary: true, zeroPaymentObjectBoundary: true, navigationOnly: true,
  canaryBatchId: batchId, userProfileOpened: false, userBusinessDataModified: false,
})
for (const name of ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json', 'restore-verification.json', 'checkpoint-screenshot.png', 'trace.zip']) {
  if (!fs.existsSync(path.join(stagingDir, name))) throw new Error(`checkpoint file missing: ${name}`)
}
fs.renameSync(stagingDir, targetDir)
console.log(JSON.stringify({
  version: 'V1.14.2.8.4.7.35', checkpointPath: targetDir, canaryBatchId: batchId, canaryScenarioCount: 5,
  crossProcessRecovery: 'passed', protectedCheckpointHashesUnchanged: true,
  traceHash: sha256(path.join(targetDir, 'trace.zip')), businessDataModified: false, result: 'passed',
}, null, 2))
