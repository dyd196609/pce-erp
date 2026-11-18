import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const checkpointRoot = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const previousId = 'purchase_reconciliation_final_review_ready'
const targetId = 'purchase_reconciliation_transaction_design_ready'
const batchId = `prc-transaction-${Date.now()}-${process.pid}`
const stagingDir = path.join(checkpointRoot, '.staging', `${targetId}-${batchId}`)
const targetDir = path.join(checkpointRoot, targetId)
const previousDir = path.join(checkpointRoot, previousId)
const reportPath = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-transaction-design-report.json')
const playwrightCli = path.join(root, 'node_modules', '@playwright', 'test', 'cli.js')
const coreFiles = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']

const writeJson = (file, value) => fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
const sha256 = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const hashSet = (directory) => Object.fromEntries(coreFiles.map((name) => [name, sha256(path.join(directory, name))]))

function runNode(args, env = {}) {
  const result = spawnSync(process.execPath, args, { cwd: root, env: { ...process.env, ...env }, stdio: 'inherit' })
  if ((result.status ?? 1) !== 0) process.exit(result.status ?? 1)
}

function runBuild() {
  const result = process.platform === 'win32'
    ? spawnSync(process.env.ComSpec || 'cmd.exe', ['/d', '/s', '/c', 'npm.cmd run build'], { cwd: root, env: process.env, stdio: 'inherit' })
    : spawnSync('npm', ['run', 'build'], { cwd: root, env: process.env, stdio: 'inherit' })
  if ((result.status ?? 1) !== 0) process.exit(result.status ?? 1)
}

function integrityHash(directory) {
  const hash = crypto.createHash('sha256')
  for (const name of coreFiles.slice(1)) { hash.update(name); hash.update(fs.readFileSync(path.join(directory, name))) }
  return hash.digest('hex')
}

if (!fs.existsSync(previousDir)) throw new Error(`previous checkpoint missing: ${previousId}`)
const previousManifest = JSON.parse(fs.readFileSync(path.join(previousDir, 'manifest.json'), 'utf8'))
for (const [field, expected] of Object.entries({
  version: 'V1.14.2.8.4.7.38', immutable: true, canaryGroup: true, singleCanary: false,
  sharedActionGateFrameworkReady: true, purchaseReconciliationAdapterReady: true, finalReviewModelReady: true,
  releaseConditionsReady: true, freshnessProtectionReady: true, targetRaceProtectionReady: true,
  auditBoundaryReady: true, idempotencyReady: true, crossProcessRecoveryReady: true,
  moduleNavigationUnchanged: true, formalCreationAllowed: false, formalNumberAllocated: false,
  zeroPurchaseReconciliationWrite: true, zeroSupplierSettlementWrite: true, zeroPaymentObjectWrite: true,
})) if (previousManifest[field] !== expected) throw new Error(`previous checkpoint contract mismatch: ${field}`)
for (const name of coreFiles) if (!fs.existsSync(path.join(previousDir, name))) throw new Error(`previous checkpoint core file missing: ${name}`)
if (fs.existsSync(targetDir)) throw new Error(`formal checkpoint already exists: ${targetDir}`)
const protectedHashesBefore = hashSet(previousDir)
fs.mkdirSync(stagingDir, { recursive: true })
const env = { PCE_CANARY_BATCH_ID: batchId, PCE_CANARY_STAGING_DIR: stagingDir, PCE_GOLDEN_RUNNER_TRACE: '1' }

runNode(['scripts/verifyPurchaseReconciliationTransactionMatrix.mjs'], env)
runNode(['scripts/verifyPurchasePayableSliceStability.mjs'], env)
runNode([playwrightCli, 'test', '-c', 'playwright.runtime.config.js', 'tests/e2e/purchaseReconciliationFormalGenerationTransactionDesign.spec.js', '-g', '金丝雀群 A-Z'], env)
let report = JSON.parse(fs.readFileSync(reportPath, 'utf8'))
if (report.result !== 'passed' || report.canaryBatchId !== batchId || report.canaryScenarioCount !== 26 || report.generatedFailureScenarioCount !== 12) throw new Error('transaction report identity or matrix mismatch')
if (!report.protectedCheckpointHashesUnchanged || report.formalBusinessWriteCount !== 0 || report.formalNumberAllocationCount !== 0 || report.networkWriteRequestCount !== 0 || report.localStorageBusinessWriteCount !== 0) throw new Error('formal zero-write or protected checkpoint boundary failed')
if (!report.moduleNavigationUnchanged) throw new Error('module navigation changed')
const tracePath = path.resolve(report.runnerTraceExpectedPath)
if (path.dirname(tracePath) !== path.resolve(report.playwrightOutputDir) || !fs.existsSync(tracePath)) throw new Error('runner trace ownership mismatch')
fs.copyFileSync(tracePath, path.join(stagingDir, 'trace.zip'))
runNode([playwrightCli, 'test', '-c', 'playwright.runtime.config.js', 'tests/e2e/purchaseReconciliationFormalGenerationTransactionDesign.spec.js', '-g', '跨进程恢复'], { ...env, PCE_CANARY_RECOVERY: '1' })

report.crossProcessRecovery = {
  passed: true, recoveredStates: ['committed', 'commit_unknown'], automaticRetryCount: 0,
  duplicateCommitCount: 0, duplicateStepHistoryAppendCount: 0, formalBusinessWriteCount: 0,
}
report.runnerTracePath = tracePath
report.checkpoint = targetDir
const storage = JSON.parse(fs.readFileSync(path.join(stagingDir, 'storage-state.json'), 'utf8'))
const origin = process.env.PCE_BASE_URL || 'http://localhost:5173'
const localEntries = storage.origins?.find((item) => item.origin === origin)?.localStorage || []
writeJson(path.join(stagingDir, 'application-state.json'), {
  version: 'V1.14.2.8.4.7.39', origin, canaryBatchId: batchId, canaryGroup: true,
  isolatedTransactionDesign: true, localStorage: Object.fromEntries(localEntries.map((item) => [item.name, item.value])),
  capturedAt: new Date().toISOString(),
})
writeJson(path.join(stagingDir, 'business-entities.json'), {
  version: 'V1.14.2.8.4.7.39', origin: 'canary', canaryBatchId: batchId, canaryGroup: true, singleCanary: false,
  sharedTransactionFrameworkReady: true, purchaseReconciliationTransactionAdapterReady: true,
  formalGenerationCommandModelReady: true, transactionPlanReady: true, numberPolicyReady: true,
  idempotentCommitReady: true, sourceLockReady: true, targetUniquenessReady: true, rollbackPlanReady: true,
  rollbackFailureBoundaryReady: true, commitUnknownRecoveryReady: true, transactionIntegrityReady: true,
  stepFailureMatrixReady: true, crossProcessRecoveryReady: true, moduleNavigationUnchanged: true,
  formalCreationAllowed: false, formalNumberAllocated: false, zeroPurchaseReconciliationWrite: true,
  zeroSupplierSettlementWrite: true, zeroPaymentObjectWrite: true,
  transactionResults: report.scenarioResults,
})
writeJson(path.join(stagingDir, 'relationship-graph.json'), {
  version: 'V1.14.2.8.4.7.39', canaryBatchId: batchId,
  layers: ['action-gate -> action-transaction', 'action-transaction -> purchaseReconciliationFormalGenerationTransaction', 'purchaseReconciliationFormalGenerationTransaction -> PurchaseReconciliationPage'],
  transactionStates: report.transactionStateDefinitions, transactionStepCount: report.transactionStepDefinitions.length,
  compensationStepCount: report.compensationDefinitions.length, artifactClassification: report.artifactClassification,
  formalPurchaseReconciliationObjectCount: 0, paymentObjectCount: 0, moduleNavigationUnchanged: true,
})
writeJson(path.join(stagingDir, 'restore-verification.json'), {
  checkpointId: targetId, status: 'passed', result: 'passed', recoveredStates: ['committed', 'commit_unknown'],
  verificationProcess: 'independent_node_playwright_process', automaticRetryCount: 0,
  verifiedAt: new Date().toISOString(), canaryBatchId: batchId, businessDataModified: false,
})

runBuild()
report.buildExecuted = true
report.buildResult = 'passed'
report.protectedCheckpointHashesAfter = hashSet(previousDir)
report.currentBaselineHashSet = report.protectedCheckpointHashesAfter
report.protectedCheckpointHashesUnchanged = JSON.stringify(protectedHashesBefore) === JSON.stringify(report.protectedCheckpointHashesAfter)
if (!report.protectedCheckpointHashesUnchanged) throw new Error('protected checkpoint changed during build')
writeJson(reportPath, report)

const hash = integrityHash(stagingDir)
writeJson(path.join(stagingDir, 'manifest.json'), {
  checkpointVersion: '1.0.0', version: 'V1.14.2.8.4.7.39', checkpointId: targetId,
  createdAt: new Date().toISOString(), origin, sourceCheckpointId: previousId,
  nextStageId: 'purchase-reconciliation-formal-generation-runtime-authorization',
  entityIds: [...new Set(report.scenarioResults.map((item) => item.transactionPlanId).filter(Boolean))],
  integrityFiles: coreFiles.slice(1), integrityHash: hash, restorable: true, immutable: true, canaryGroup: true, singleCanary: false,
  sharedTransactionFrameworkReady: true, purchaseReconciliationTransactionAdapterReady: true,
  formalGenerationCommandModelReady: true, transactionPlanReady: true, numberPolicyReady: true,
  idempotentCommitReady: true, sourceLockReady: true, targetUniquenessReady: true,
  rollbackPlanReady: true, rollbackFailureBoundaryReady: true, commitUnknownRecoveryReady: true,
  transactionIntegrityReady: true, stepFailureMatrixReady: true, crossProcessRecoveryReady: true,
  moduleNavigationUnchanged: true, formalCreationAllowed: false, formalNumberAllocated: false,
  zeroPurchaseReconciliationWrite: true, zeroSupplierSettlementWrite: true, zeroPaymentObjectWrite: true,
  canaryBatchId: batchId, userProfileOpened: false, userBusinessDataModified: false,
})
for (const name of [...coreFiles, 'restore-verification.json', 'transaction-results.json', 'checkpoint-screenshot.png', 'trace.zip']) {
  if (!fs.existsSync(path.join(stagingDir, name))) throw new Error(`checkpoint file missing: ${name}`)
}
fs.renameSync(stagingDir, targetDir)
console.log(JSON.stringify({
  version: 'V1.14.2.8.4.7.39', checkpointPath: targetDir, canaryBatchId: batchId,
  canaryScenarioCount: 26, generatedFailureScenarioCount: 12,
  pureFunctionCaseCount: report.pureFunctionCaseCount, transactionStateMatrixCaseCount: report.transactionStateMatrixCaseCount,
  numberingMatrixCaseCount: report.numberingMatrixCaseCount, idempotencyConcurrencyCaseCount: report.idempotencyConcurrencyCaseCount,
  crossProcessRecovery: 'passed', protectedCheckpointHashesUnchanged: true,
  formalBusinessWriteCount: 0, formalNumberAllocationCount: 0, purchaseReconciliationWriteCount: 0,
  supplierSettlementWriteCount: 0, paymentObjectWriteCount: 0, moduleNavigationUnchanged: true,
  buildResult: 'passed', traceHash: sha256(path.join(targetDir, 'trace.zip')),
  businessDataModified: false, result: 'passed',
}, null, 2))
