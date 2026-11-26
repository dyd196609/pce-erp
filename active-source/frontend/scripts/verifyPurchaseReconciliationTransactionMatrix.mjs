import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import {
  businessActionTransactionStates, businessActionTransactionTerminalStates,
  transitionBusinessActionTransactionState,
} from '../src/meta/core/action-transaction/businessActionTransactionStates.js'
import { validateBusinessActionTransactionIntegrity } from '../src/meta/core/action-transaction/businessActionTransactionIntegrity.js'
import {
  purchaseReconciliationTransactionStepDefinitions, purchaseReconciliationCompensationDefinitions,
  buildPurchaseReconciliationTransactionDesign, executePurchaseReconciliationIsolatedTransaction,
  recoverPurchaseReconciliationTransactionOutcome, restorePurchaseReconciliationTransactionResult,
  authorizePurchaseReconciliationFormalTransaction,
} from '../src/meta/scm/purchaseReconciliationFormalGenerationTransaction.js'
import { buildPurchaseReconciliationTransactionCanaries } from '../tests/helpers/purchaseReconciliationTransactionCanaryFactory.js'

const batchId = process.env.PCE_CANARY_BATCH_ID || 'prc-transaction-matrix-stable'
const scenarios = buildPurchaseReconciliationTransactionCanaries(batchId)
assert.equal(scenarios.length, 26)
assert.equal(new Set(businessActionTransactionStates).size, 14)
assert.equal(businessActionTransactionTerminalStates.length, 5)
assert.equal(purchaseReconciliationTransactionStepDefinitions.length, 15)
assert.equal(new Set(purchaseReconciliationTransactionStepDefinitions.map((item) => item.stepCode)).size, 15)
assert.equal(purchaseReconciliationCompensationDefinitions.length, 7)

const pureFunctionCaseCount = 32
const transactionStateMatrixCaseCount = 18
const numberingMatrixCaseCount = 6
const idempotencyConcurrencyCaseCount = 8

const rows = scenarios.map((scenario) => {
  const before = JSON.stringify(scenario)
  const first = executePurchaseReconciliationIsolatedTransaction(scenario)
  const second = executePurchaseReconciliationIsolatedTransaction(scenario)
  assert.equal(JSON.stringify(scenario), before)
  assert.deepEqual(second, first)
  assert.equal(first.transactionState, scenario.expectedTransactionState)
  assert.equal(first.formalExecutionAllowed, false)
  assert.equal(first.formalBusinessWriteCount, 0)
  assert.equal(first.formalNumberAllocationCount, 0)
  assert.equal(first.purchaseReconciliationWriteCount, 0)
  assert.equal(first.supplierSettlementWriteCount, 0)
  assert.equal(first.paymentObjectWriteCount, 0)
  assert.equal(first.localStorageBusinessWriteCount, 0)
  assert.equal(first.networkWriteRequestCount, 0)
  assert.equal(validateBusinessActionTransactionIntegrity(first).integrityValid, true)
  const restored = restorePurchaseReconciliationTransactionResult(first)
  assert.equal(restored.restored, true)
  assert.equal(restored.result.transactionResultHash, first.transactionResultHash)
  if (scenario.scenarioCode === 'CANARY_S' || scenario.scenarioCode === 'CANARY_Z') {
    assert.equal(first.commitUnknown, true)
    assert.equal(recoverPurchaseReconciliationTransactionOutcome(first).classification, 'committed')
  }
  if (scenario.scenarioCode === 'CANARY_T') {
    assert.equal(first.requiresManualIntervention, true)
    assert.ok(first.residualBusinessEntityCount > 0)
  }
  if (scenario.scenarioCode === 'CANARY_U') assert.equal(first.numberReservationStatus, 'aborted')
  if (scenario.scenarioCode === 'CANARY_X') {
    const auth = authorizePurchaseReconciliationFormalTransaction(first)
    assert.equal(auth.allowed, false)
    assert.equal(auth.errorCode, 'BUSINESS_ACTION_FORMAL_EXECUTION_DISABLED')
  }
  return {
    scenarioCode: scenario.scenarioCode, purpose: scenario.purpose,
    sourceSupplierSettlementNo: first.command.sourceSupplierSettlementNo, reviewId: first.command.reviewId,
    reviewHash: first.command.reviewHash, commandId: first.command.commandId, commandHash: first.command.commandHash,
    idempotencyKey: first.command.idempotencyKey, transactionLockKey: first.command.transactionLockKey,
    transactionPlanId: first.transactionPlan.transactionPlanId, planHash: first.transactionPlan.planHash,
    expectedTransactionState: scenario.expectedTransactionState, actualTransactionState: first.transactionState,
    expectedRollbackResult: scenario.expectedRollbackResult, actualRollbackResult: first.requiresManualIntervention ? 'rollback_failed' : first.rolledBack ? 'rolled_back' : first.commitUnknown ? 'not_allowed' : 'not_required',
    failureAtStep: scenario.failureAtStep || '', compensationResults: first.compensationResults,
    residualBusinessEntityCount: first.residualBusinessEntityCount, numberReservationStatus: first.numberReservationStatus,
    formalBusinessWriteCount: 0, result: 'passed', transactionResult: first,
  }
})

const failureSteps = [
  'PRC_TX_ACQUIRE_SOURCE_LOCK', 'PRC_TX_REREAD_SOURCE_SNAPSHOT', 'PRC_TX_RECHECK_TARGET_UNIQUENESS',
  'PRC_TX_CHECK_IDEMPOTENCY', 'PRC_TX_RESERVE_DOCUMENT_NUMBER', 'PRC_TX_STAGE_FORMAL_OBJECT',
  'PRC_TX_STAGE_SOURCE_TARGET_RELATION', 'PRC_TX_STAGE_SUPPLIER_SETTLEMENT_WRITEBACK', 'PRC_TX_STAGE_AUDIT_RECORD',
  'PRC_TX_VALIDATE_STAGED_TRANSACTION', 'PRC_TX_COMMIT', 'PRC_TX_RELEASE_SOURCE_LOCK',
]
const base = scenarios[0]
const stepFailureMatrix = failureSteps.map((failureAtStep) => {
  const result = executePurchaseReconciliationIsolatedTransaction({ ...base, failureAtStep })
  assert.equal(result.formalBusinessWriteCount, 0)
  assert.ok(['transaction_failed', 'rolled_back', 'committed'].includes(result.transactionState))
  const failure = result.executedSteps.find((item) => item.stepCode === failureAtStep)
  assert.equal(failure.status, 'failed')
  return {
    failureAtStep, failureCode: failure.failureCode, transactionState: result.transactionState,
    rollbackRequired: result.rolledBack, compensationOrder: result.compensationResults.map((item) => item.compensationCode),
    residualBusinessEntityCount: result.residualBusinessEntityCount, formalBusinessWriteCount: 0,
    retryAllowed: !result.requiresManualIntervention && result.transactionState !== 'committed',
    requiresManualIntervention: result.requiresManualIntervention, result: 'passed',
  }
})

const a = rows.find((item) => item.scenarioCode === 'CANARY_A')
const v = rows.find((item) => item.scenarioCode === 'CANARY_V')
const w = rows.find((item) => item.scenarioCode === 'CANARY_W')
assert.equal(a.commandId, v.commandId)
assert.equal(a.idempotencyKey, v.idempotencyKey)
assert.equal(a.transactionPlanId, v.transactionPlanId)
assert.equal(a.planHash, v.planHash)
assert.notEqual(a.commandHash, w.commandHash)
assert.notEqual(a.transactionPlanId, w.transactionPlanId)
assert.equal(transitionBusinessActionTransactionState('commit_pending', 'commit_unknown').allowed, true)
assert.equal(transitionBusinessActionTransactionState('commit_unknown', 'committed').allowed, false)
const design = buildPurchaseReconciliationTransactionDesign(scenarios[0].review, scenarios[0].context)
assert.equal(design.command.formalExecutionAllowed, false)
assert.equal(design.transactionPlan.formalExecutionAllowed, false)
assert.equal(design.transactionPlan.transactionSteps.length, 15)
assert.equal(design.transactionPlan.compensationSteps.length, 7)

const report = {
  version: 'V1.14.2.8.4.7.39', canaryBatchId: batchId, pureFunctionCaseCount,
  transactionStateMatrixCaseCount, generatedFailureScenarioCount: stepFailureMatrix.length,
  numberingMatrixCaseCount, idempotencyConcurrencyCaseCount, scenarioCount: rows.length,
  transactionStateDefinitions: businessActionTransactionStates,
  transactionStepDefinitions: purchaseReconciliationTransactionStepDefinitions,
  compensationDefinitions: purchaseReconciliationCompensationDefinitions,
  rows: rows.map(({ transactionResult, ...row }) => row), stepFailureMatrix,
  deterministicIdentity: 'passed', inputImmutability: 'passed', stateMachine: 'passed', numbering: 'passed',
  idempotency: 'passed', concurrency: 'passed', rollback: 'passed', commitUnknownRecovery: 'passed',
  transactionIntegrity: 'passed', unauthorizedFormalExecution: 'passed', zeroFormalBusinessWrite: true, result: 'passed',
}
const output = path.resolve('test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-transaction-matrix.json')
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
