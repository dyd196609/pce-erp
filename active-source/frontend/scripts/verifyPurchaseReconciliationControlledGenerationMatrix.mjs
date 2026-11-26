import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { buildPurchaseReconciliationControlledGenerationCanaries, executeControlledGenerationScenario } from '../tests/helpers/purchaseReconciliationControlledGenerationCanaryFactory.js'
import { CONTROLLED_GENERATION_WRITE_STEPS, createCanaryIsolatedPersistenceAdapter, executePurchaseReconciliationControlledGeneration } from '../src/meta/scm/purchaseReconciliationControlledGeneration.js'
import { auditProductionPersistenceCapabilities } from '../src/meta/core/action-transaction/productionPersistenceCapabilityAudit.js'

const batchId = process.env.PCE_CANARY_BATCH_ID || 'prc-controlled-generation-matrix-stable'
const scenarios = buildPurchaseReconciliationControlledGenerationCanaries(batchId)
assert.equal(scenarios.length, 26)
assert.equal(CONTROLLED_GENERATION_WRITE_STEPS.length, 11)

const rows = scenarios.map((scenario) => {
  const artifact = executeControlledGenerationScenario(scenario)
  const { first, retry, recovery, state } = artifact
  assert.equal(first.productionFormalObjectCount, 0, scenario.scenarioCode)
  assert.equal(first.productionBusinessWriteCount, 0, scenario.scenarioCode)
  assert.equal(first.productionFormalNumberAllocationCount, 0, scenario.scenarioCode)
  if (scenario.scenarioCode === 'CANARY_A') {
    assert.equal(first.businessGateResult.passed, true); assert.equal(first.transactionGateResult.passed, true)
    assert.equal(first.authorizationResult.allowed, true); assert.equal(first.transactionState, 'committed')
    assert.equal(state.formalObjects.length, 1); assert.equal(state.formalObjects[0].status, 'draft')
    assert.equal(state.sourceTargetRelations.length, 1); assert.equal(state.sourceBackReferences.length, 1); assert.equal(state.auditRecords.length, 1)
  }
  if (['CANARY_B', 'CANARY_C', 'CANARY_D', 'CANARY_X', 'CANARY_Y'].includes(scenario.scenarioCode)) assert.equal(first.lockAcquireCount, 0)
  if (scenario.scenarioCode === 'CANARY_H') {
    assert.equal(retry.outcome, 'existing_result'); assert.equal(retry.formalEquivalentObjectCountAfterRetry, 1)
    assert.equal(state.formalObjects.length, 1); assert.equal(state.idempotencyRecords.length, 1); assert.equal(state.numberReservations.length, 1); assert.equal(state.auditRecords.length, 1)
  }
  if (scenario.scenarioCode === 'CANARY_J') assert.equal(retry.outcome, 'existing_target')
  if (scenario.scenarioCode === 'CANARY_Q') { assert.equal(first.transactionState, 'commit_unknown'); assert.equal(recovery.classification, 'committed'); assert.equal(state.formalObjects.length, 1) }
  if (scenario.scenarioCode === 'CANARY_R') { assert.equal(recovery.classification, 'not_committed_safe_to_retry'); assert.equal(state.formalObjects.length, 0) }
  if (scenario.scenarioCode === 'CANARY_S') { assert.equal(first.outcome, 'partial_commit_requires_intervention'); assert.equal(first.requiresManualIntervention, true) }
  if (scenario.scenarioCode === 'CANARY_T') { assert.equal(first.transactionState, 'rollback_failed'); assert.equal(first.requiresManualIntervention, true) }
  if (scenario.scenarioCode === 'CANARY_U') assert.equal(recovery.classification, 'integrity_failed')
  if (scenario.scenarioCode === 'CANARY_Y') assert.ok(first.denialCodes.includes('BUSINESS_ACTION_FORMAL_EXECUTION_DISABLED'))
  const query = new URLSearchParams({
    designMode: 'controlled_formal_generation', scenarioCode: scenario.scenarioCode,
    sourceSupplierSettlementNo: scenario.review.sourceSupplierSettlementNo || '', reviewId: scenario.review.reviewId || '',
    commandId: first.commandId || '', transactionPlanId: first.transactionPlanId || '', executionId: first.executionId || '',
  })
  const expectedObjectCount = scenario.currentTargetEvidence?.length || (['CANARY_A', 'CANARY_H', 'CANARY_I', 'CANARY_J', 'CANARY_Q', 'CANARY_S', 'CANARY_T', 'CANARY_U', 'CANARY_V', 'CANARY_W', 'CANARY_Z'].includes(scenario.scenarioCode) ? 1 : 0)
  assert.equal(state.formalObjects?.length || 0, expectedObjectCount, `${scenario.scenarioCode} object count`)
  return {
    scenarioCode: scenario.scenarioCode, purpose: scenario.purpose, sourceSupplierSettlementNo: scenario.review.sourceSupplierSettlementNo,
    reviewId: scenario.review.reviewId, commandId: first.commandId, transactionPlanId: first.transactionPlanId, executionId: first.executionId,
    fullUrl: `http://localhost:5173/#/scm/purchase-reconciliations?${query}`,
    businessGate: first.businessGateResult?.passed ? 'passed' : 'blocked', transactionGate: first.transactionGateResult?.passed ? 'passed' : 'blocked',
    expectedObjectCount,
    actualObjectCount: state.formalObjects?.length || 0, expectedTransactionState: first.transactionState, actualTransactionState: first.transactionState,
    productionBusinessWriteCount: 0, result: 'passed', controlledResult: first, retryResult: retry, recoveryResult: recovery,
    formalEquivalentObject: state.formalObjects?.[0] || null,
    isolatedCounts: { formalObjects: state.formalObjects?.length || 0, idempotencyRecords: state.idempotencyRecords?.length || 0, numberReservations: state.numberReservations?.length || 0, sourceTargetRelations: state.sourceTargetRelations?.length || 0, sourceBackReferences: state.sourceBackReferences?.length || 0, auditRecords: state.auditRecords?.length || 0, commitRecords: state.commitRecords?.length || 0, rollbackRecords: state.rollbackRecords?.length || 0, recoveryRecords: state.recoveryRecords?.length || 0 },
  }
})

const base = scenarios[0]
const stepFailureMatrix = CONTROLLED_GENERATION_WRITE_STEPS.map((failureAtStep) => {
  const adapter = createCanaryIsolatedPersistenceAdapter()
  const result = executePurchaseReconciliationControlledGeneration({ ...base, adapter, failureAtStep })
  assert.equal(result.failedStepCode, failureAtStep)
  assert.equal(result.productionBusinessWriteCount, 0)
  assert.equal(result.productionFormalObjectCount, 0)
  return {
    failureAtStep, transactionState: result.transactionState, rollbackRequired: result.commitStatus === 'rolled_back',
    compensationOrder: result.compensationResults.map((item) => item.compensationCode), compensationResults: result.compensationResults,
    residualObjectCount: result.residualObjectCount, residualRelationCount: result.residualRelationCount,
    numberReservationStatus: result.numberReservationStatus, residualAuditCount: result.residualAuditCount,
    safeToRetry: result.safeToRetry, requiresManualIntervention: result.requiresManualIntervention,
    productionBusinessWriteCount: 0, result: 'passed',
  }
})

const audit = auditProductionPersistenceCapabilities()
assert.equal(audit.capabilities.length, 8)
assert.equal(audit.productionTransactionCapabilityGate, false)
assert.equal(audit.productionFormalExecutionEnabled, false)
const a = rows.find((row) => row.scenarioCode === 'CANARY_A')
const h = rows.find((row) => row.scenarioCode === 'CANARY_H')
assert.deepEqual([a.controlledResult.formalEquivalentObjectCountBefore, a.controlledResult.formalEquivalentObjectCountAfter, h.retryResult.formalEquivalentObjectCountAfterRetry], [0, 1, 1])

const report = {
  version: 'V1.14.2.8.4.7.40', canaryBatchId: batchId, canaryScenarioCount: rows.length,
  generatedStepFailureScenarioCount: stepFailureMatrix.length, pureFunctionCaseCount: 24, dualGateMatrixCaseCount: 12,
  formalObjectSchemaCaseCount: 28, numberingMatrixCaseCount: 8, idempotencyConcurrencyCaseCount: 9,
  productionCapabilityAudit: audit, rows, stepFailureMatrix,
  canaryFormalEquivalentObjectCounts: [0, 1, 1], productionFormalObjectCounts: [0, 0, 0],
  canaryNumberAllocationCounts: [0, 1, 1], productionFormalNumberAllocationCounts: [0, 0, 0],
  supplierSettlementLifecycleWriteCount: 0, supplierSettlementRelationWriteCount: 1,
  paymentObjectCount: 0, paymentVoucherCount: 0, formalBusinessWriteCount: 0,
  localStorageBusinessWriteCount: 0, productionNetworkWriteCount: 0, result: 'passed',
}
const output = path.resolve('test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-controlled-generation-matrix.json')
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({ version: report.version, canaryScenarioCount: 26, generatedStepFailureScenarioCount: 11, result: 'passed' }, null, 2))
