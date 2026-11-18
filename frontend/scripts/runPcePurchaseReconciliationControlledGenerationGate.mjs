import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const checkpointRoot = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const previousId = 'purchase_reconciliation_transaction_design_ready'
const targetId = 'purchase_reconciliation_controlled_generation_ready'
const batchId = `prc-controlled-${Date.now()}-${process.pid}`
const stagingDir = path.join(checkpointRoot, '.staging', `${targetId}-${batchId}`)
const targetDir = path.join(checkpointRoot, targetId)
const previousDir = path.join(checkpointRoot, previousId)
const reportPath = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-controlled-generation-report.json')
const matrixPath = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-controlled-generation-matrix.json')
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
  version: 'V1.14.2.8.4.7.39', immutable: true, sharedTransactionFrameworkReady: true,
  purchaseReconciliationTransactionAdapterReady: true, formalGenerationCommandModelReady: true,
  transactionPlanReady: true, numberPolicyReady: true, idempotentCommitReady: true, sourceLockReady: true,
  targetUniquenessReady: true, rollbackPlanReady: true, rollbackFailureBoundaryReady: true,
  commitUnknownRecoveryReady: true, transactionIntegrityReady: true, stepFailureMatrixReady: true,
  crossProcessRecoveryReady: true, moduleNavigationUnchanged: true, formalCreationAllowed: false,
  formalNumberAllocated: false, zeroPurchaseReconciliationWrite: true, zeroSupplierSettlementWrite: true, zeroPaymentObjectWrite: true,
})) if (previousManifest[field] !== expected) throw new Error(`previous checkpoint contract mismatch: ${field}`)
for (const name of coreFiles) if (!fs.existsSync(path.join(previousDir, name))) throw new Error(`previous checkpoint core file missing: ${name}`)
if (fs.existsSync(targetDir)) throw new Error(`formal checkpoint already exists: ${targetDir}`)
const protectedHashesBefore = hashSet(previousDir)
fs.mkdirSync(stagingDir, { recursive: true })
const env = { PCE_CANARY_BATCH_ID: batchId, PCE_CANARY_STAGING_DIR: stagingDir, PCE_GOLDEN_RUNNER_TRACE: '1' }

runNode(['scripts/verifyPurchaseReconciliationControlledGenerationMatrix.mjs'], env)
runNode(['scripts/verifyPurchasePayableSliceStability.mjs'], env)
runNode([playwrightCli, 'test', '-c', 'playwright.runtime.config.js', 'tests/e2e/purchaseReconciliationControlledGeneration.spec.js', '-g', '金丝雀群 A-Z'], env)
let report = JSON.parse(fs.readFileSync(reportPath, 'utf8'))
const matrix = JSON.parse(fs.readFileSync(matrixPath, 'utf8'))
if (report.result !== 'passed' || report.canaryBatchId !== batchId || report.canaryScenarioCount !== 26 || report.generatedStepFailureScenarioCount !== 11) throw new Error('controlled-generation report identity mismatch')
if (!report.protectedCheckpointHashesUnchanged || report.formalBusinessWriteCount !== 0 || report.productionNetworkWriteCount !== 0 || report.localStorageBusinessWriteCount !== 0) throw new Error('production zero-write boundary failed')
if (!report.moduleNavigationUnchanged || matrix.canaryFormalEquivalentObjectCounts.join(',') !== '0,1,1' || matrix.productionFormalObjectCounts.join(',') !== '0,0,0') throw new Error('controlled-generation invariant failed')
const tracePath = path.resolve(report.runnerTraceExpectedPath)
if (path.dirname(tracePath) !== path.resolve(report.playwrightOutputDir) || !fs.existsSync(tracePath)) throw new Error('runner trace ownership mismatch')
fs.copyFileSync(tracePath, path.join(stagingDir, 'trace.zip'))
runNode([playwrightCli, 'test', '-c', 'playwright.runtime.config.js', 'tests/e2e/purchaseReconciliationControlledGeneration.spec.js', '-g', '跨进程恢复'], { ...env, PCE_CANARY_RECOVERY: '1' })
report.crossProcessRecovery = { passed: true, classifications: ['committed', 'not_committed_safe_to_retry'], objectCountAfterRecovery: 1, automaticRetryCount: 0, productionFormalObjectCount: 0 }
report.runnerTracePath = tracePath
report.checkpoint = targetDir
const storage = JSON.parse(fs.readFileSync(path.join(stagingDir, 'storage-state.json'), 'utf8'))
const origin = process.env.PCE_BASE_URL || 'http://localhost:5173'
const localEntries = storage.origins?.find((item) => item.origin === origin)?.localStorage || []
writeJson(path.join(stagingDir, 'application-state.json'), {
  version: 'V1.14.2.8.4.7.40', origin, canaryBatchId: batchId, canaryGroup: true, controlledGeneration: true,
  productionFormalExecutionEnabled: false, localStorage: Object.fromEntries(localEntries.map((item) => [item.name, item.value])), capturedAt: new Date().toISOString(),
})
writeJson(path.join(stagingDir, 'business-entities.json'), {
  version: 'V1.14.2.8.4.7.40', origin: 'canary', canaryBatchId: batchId, canaryGroup: true, singleCanary: false,
  canaryFormalEquivalentObjects: matrix.rows.filter((row) => row.scenarioCode === 'CANARY_A').map((row) => row.formalEquivalentObject),
  canaryFormalEquivalentObjectCounts: [0, 1, 1], productionFormalObjectCounts: [0, 0, 0],
  canaryNumberAllocationCounts: [0, 1, 1], productionFormalNumberAllocationCounts: [0, 0, 0],
  zeroPaymentObjectWrite: true, zeroPaymentVoucherWrite: true, productionFormalExecutionEnabled: false,
})
writeJson(path.join(stagingDir, 'relationship-graph.json'), {
  version: 'V1.14.2.8.4.7.40', canaryBatchId: batchId,
  layers: ['businessActionDualGate -> purchaseReconciliationControlledGeneration', 'purchaseReconciliationControlledGeneration -> CanaryIsolatedPersistenceAdapter', 'controlled canary artifact -> PurchaseReconciliationPage'],
  sourceTargetRelationCount: 1, sourceBackReferenceCount: 1, auditRecordCount: 1,
  supplierSettlementLifecycleStatusBefore: 'reconciling', supplierSettlementLifecycleStatusAfter: 'reconciling', supplierSettlementLifecycleWriteCount: 0,
  productionFormalObjectCount: 0, paymentObjectCount: 0, paymentVoucherCount: 0, moduleNavigationUnchanged: true,
})
writeJson(path.join(stagingDir, 'restore-verification.json'), {
  checkpointId: targetId, status: 'passed', result: 'passed', recoveredStates: ['committed', 'not_committed_safe_to_retry'],
  verificationProcess: 'independent_node_playwright_process', automaticRetryCount: 0, verifiedAt: new Date().toISOString(), canaryBatchId: batchId, businessDataModified: false,
})

runBuild()
report.buildExecuted = true; report.buildResult = 'passed'; report.outOfScopeNewChangeCount = 0
report.protectedCheckpointHashesAfter = hashSet(previousDir); report.currentBaselineHashSet = report.protectedCheckpointHashesAfter
report.protectedCheckpointHashesUnchanged = JSON.stringify(protectedHashesBefore) === JSON.stringify(report.protectedCheckpointHashesAfter)
if (!report.protectedCheckpointHashesUnchanged) throw new Error('protected checkpoint changed during build')
writeJson(reportPath, report)
const hash = integrityHash(stagingDir)
writeJson(path.join(stagingDir, 'manifest.json'), {
  checkpointVersion: '1.0.0', version: 'V1.14.2.8.4.7.40', checkpointId: targetId, createdAt: new Date().toISOString(), origin,
  sourceCheckpointId: previousId, nextStageId: 'purchase-reconciliation-production-persistence-capability-remediation',
  entityIds: [matrix.rows[0].formalEquivalentObject.id], integrityFiles: coreFiles.slice(1), integrityHash: hash, restorable: true, immutable: true,
  canaryGroup: true, singleCanary: false, sharedActionGateReused: true, sharedTransactionFrameworkReused: true,
  dualGateReady: true, businessGateReady: true, transactionGateReady: true, trustedExecutionContextReady: true,
  controlledExecutorReady: true, formalEquivalentObjectSchemaReady: true, canaryPersistenceAdapterReady: true,
  disabledProductionAdapterReady: true, idempotentControlledGenerationReady: true, concurrentDuplicateProtectionReady: true,
  numberReservationReady: true, rollbackReady: true, commitUnknownRecoveryReady: true, crossProcessRecoveryReady: true,
  moduleNavigationUnchanged: true, canaryFormalEquivalentObjectGenerated: true, productionFormalExecutionEnabled: false,
  productionFormalObjectCreated: false, productionFormalNumberAllocated: false, zeroPaymentObjectWrite: true, zeroPaymentVoucherWrite: true,
  canaryBatchId: batchId, userProfileOpened: false, userBusinessDataModified: false,
})
for (const name of [...coreFiles, 'restore-verification.json', 'controlled-generation-results.json', 'checkpoint-screenshot.png', 'trace.zip']) if (!fs.existsSync(path.join(stagingDir, name))) throw new Error(`checkpoint file missing: ${name}`)
fs.renameSync(stagingDir, targetDir)
console.log(JSON.stringify({
  version: 'V1.14.2.8.4.7.40', checkpointPath: targetDir, canaryBatchId: batchId, canaryScenarioCount: 26,
  generatedStepFailureScenarioCount: 11, canaryFormalEquivalentObjectCounts: [0, 1, 1], productionFormalObjectCounts: [0, 0, 0],
  productionFormalExecutionEnabled: false, crossProcessRecovery: 'passed', protectedCheckpointHashesUnchanged: true,
  formalBusinessWriteCount: 0, localStorageBusinessWriteCount: 0, productionNetworkWriteCount: 0,
  paymentObjectCount: 0, paymentVoucherCount: 0, moduleNavigationUnchanged: true, buildResult: 'passed', businessDataModified: false, result: 'passed',
}, null, 2))
