import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { businessActionReviewStates, businessActionReviewDecisions, businessActionConditionCategories } from '../src/meta/core/action-gate/businessActionGateStates.js'
import {
  purchaseReconciliationFinalConditionDefinitions, buildPurchaseReconciliationFinalReview,
  validatePurchaseReconciliationFinalReviewIntegrity, restorePurchaseReconciliationFinalReview,
  authorizePurchaseReconciliationFormalGeneration,
} from '../src/meta/scm/purchaseReconciliationFinalReview.js'
import { buildPurchaseReconciliationFinalReviewCanaries } from '../tests/helpers/purchaseReconciliationFinalReviewCanaryFixtures.js'

const batchId = process.env.PCE_CANARY_BATCH_ID || 'prc-final-review-matrix-stable'
const scenarios = buildPurchaseReconciliationFinalReviewCanaries(batchId)
assert.equal(scenarios.length, 15)
assert.equal(new Set(businessActionReviewStates).size, 6)
assert.equal(new Set(businessActionReviewDecisions).size, 4)
assert.equal(new Set(purchaseReconciliationFinalConditionDefinitions.map((item) => item.code)).size, 25)
assert.equal(purchaseReconciliationFinalConditionDefinitions.length, 25)
assert.ok(businessActionConditionCategories.length >= 13)

const rows = scenarios.map((scenario) => {
  const before = JSON.stringify(scenario)
  const review = buildPurchaseReconciliationFinalReview(scenario)
  const repeated = buildPurchaseReconciliationFinalReview(scenario)
  assert.equal(JSON.stringify(scenario), before)
  assert.deepEqual(repeated, review)
  assert.equal(review.reviewState, scenario.expectedReviewState)
  assert.equal(review.reviewDecision, scenario.expectedReviewDecision)
  assert.equal(review.runtimeFormalCreationAllowed, false)
  assert.equal(review.formalBusinessWriteCount, 0)
  assert.equal(review.formalNumberAllocationCount, 0)
  assert.equal(review.purchaseReconciliationWriteCount, 0)
  assert.equal(review.supplierSettlementWriteCount, 0)
  assert.equal(review.paymentObjectWriteCount, 0)
  assert.equal(review.conditionResults.length, 25)
  assert.deepEqual(review.conditionResults.map((item) => item.code), purchaseReconciliationFinalConditionDefinitions.map((item) => item.code))
  if (scenario.expectedBlockingCode) assert.ok(review.unmetConditions.some((item) => item.code === scenario.expectedBlockingCode))
  if (scenario.expectedTargetStatus) assert.equal(review.targetExistenceStatus, scenario.expectedTargetStatus)
  if (scenario.scenarioCode === 'CANARY_D') assert.equal(review.integrityResult, 'invalid')
  if (['CANARY_E', 'CANARY_F', 'CANARY_M'].includes(scenario.scenarioCode)) assert.equal(review.freshnessResult.status, 'stale')
  const integrity = validatePurchaseReconciliationFinalReviewIntegrity(review)
  assert.equal(integrity.integrityValid, true)
  const restored = restorePurchaseReconciliationFinalReview(review)
  assert.equal(restored.restored, true)
  assert.equal(restored.review.reviewId, review.reviewId)
  assert.equal(restored.review.reviewHash, review.reviewHash)
  if (scenario.scenarioCode === 'CANARY_N') {
    const authorization = authorizePurchaseReconciliationFormalGeneration(review)
    assert.deepEqual(authorization, { allowed: false, requestedActionCode: 'purchase_reconciliation_generation', reviewDecision: 'approved', runtimeFormalCreationAllowed: false, errorCode: 'BUSINESS_ACTION_FORMAL_EXECUTION_DISABLED', formalBusinessWriteCount: 0, formalNumberAllocationCount: 0 })
  }
  return {
    scenarioCode: scenario.scenarioCode, purpose: scenario.purpose, sourceSupplierSettlementNo: review.sourceSupplierSettlementNo,
    simulationResultId: review.simulationResultId, reviewId: review.reviewId, reviewInputHash: review.reviewInputHash, reviewHash: review.reviewHash,
    expectedReviewState: scenario.expectedReviewState, actualReviewState: review.reviewState,
    expectedReviewDecision: scenario.expectedReviewDecision, actualReviewDecision: review.reviewDecision,
    freshnessStatus: review.freshnessResult.status, targetExistenceStatus: review.targetExistenceStatus,
    unmetConditionCodes: review.unmetConditions.map((item) => item.code), integrityResult: review.integrityResult,
    formalBusinessWriteCount: 0, result: 'passed',
  }
})

const byCode = Object.fromEntries(rows.map((row) => [row.scenarioCode, row]))
for (const code of ['CANARY_J', 'CANARY_L', 'CANARY_N']) {
  assert.equal(byCode.CANARY_A.reviewId, byCode[code].reviewId)
  assert.equal(byCode.CANARY_A.reviewHash, byCode[code].reviewHash)
}
assert.notEqual(byCode.CANARY_A.reviewInputHash, byCode.CANARY_K.reviewInputHash)
assert.notEqual(byCode.CANARY_A.reviewId, byCode.CANARY_K.reviewId)

const report = {
  version: 'V1.14.2.8.4.7.38', canaryBatchId: batchId, pureFunctionCaseCount: 24,
  matrixCaseCount: rows.length, reviewStateCount: 6, reviewDecisionCount: 4, conditionCount: 25,
  rows, conditionDefinitions: purchaseReconciliationFinalConditionDefinitions.map(({ code, name, category, sourceField }) => ({ code, name, category, sourceField })),
  deterministicIdentity: 'passed', inputImmutability: 'passed', sourceFreshness: 'passed', targetRace: 'passed',
  idempotency: 'passed', integrity: 'passed', unauthorizedFormalGeneration: 'passed', zeroFormalBusinessWrite: true, result: 'passed',
}
const output = path.resolve('test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-final-review-matrix.json')
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
