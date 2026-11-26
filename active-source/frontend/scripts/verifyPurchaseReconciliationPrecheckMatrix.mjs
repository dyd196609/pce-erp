import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import {
  buildPurchaseReconciliationPrecheckResult,
  purchaseReconciliationEligibilityStatuses,
  purchaseReconciliationEvidenceStatuses,
  purchaseReconciliationPrecheckRuleCodes,
  purchaseReconciliationTargetExistenceStatuses,
} from '../src/meta/scm/purchaseReconciliationCandidate.js'
import { buildPurchaseReconciliationCanaryScenarios } from '../tests/helpers/purchaseReconciliationCanaryFixtures.js'

const root = process.cwd()
const batchId = process.env.PCE_CANARY_BATCH_ID || 'canary-matrix-20260722000000'
const scenarios = buildPurchaseReconciliationCanaryScenarios(batchId)
const results = []
assert.equal(new Set(purchaseReconciliationPrecheckRuleCodes).size, purchaseReconciliationPrecheckRuleCodes.length, 'rule codes must be unique')

for (const scenario of scenarios) {
  const snapshot = JSON.stringify(scenario)
  const first = buildPurchaseReconciliationPrecheckResult(scenario)
  const second = buildPurchaseReconciliationPrecheckResult(scenario)
  assert.deepEqual(first, second, `${scenario.scenarioCode} pure result must be deterministic`)
  assert.equal(JSON.stringify(scenario), snapshot, `${scenario.scenarioCode} input mutated`)
  assert.equal(first.rules.length, purchaseReconciliationPrecheckRuleCodes.length, `${scenario.scenarioCode} rule count changed`)
  assert.deepEqual(first.rules.map((item) => item.code), purchaseReconciliationPrecheckRuleCodes, `${scenario.scenarioCode} rule order changed`)
  assert.ok(purchaseReconciliationEvidenceStatuses.includes(first.evidenceStatus))
  assert.ok(purchaseReconciliationEligibilityStatuses.includes(first.businessEligibility))
  assert.ok(purchaseReconciliationTargetExistenceStatuses.includes(first.targetExistenceStatus))
  assert.equal(first.evidenceStatus, scenario.expectedEvidenceStatus)
  assert.equal(first.businessEligibility, scenario.expectedBusinessEligibility)
  assert.equal(first.targetExistenceStatus, scenario.expectedTargetExistenceStatus)
  assert.equal(first.runtimeExecutionAllowed, false)
  assert.ok(Object.values(first.writeMetrics).every((value) => value === 0))
  if (scenario.expectedBlockingCode) assert.ok(first.candidate.blockingReasonCodes.includes(scenario.expectedBlockingCode))
  if (scenario.scenarioCode === 'CANARY_C') {
    assert.equal(first.targetCount, 2)
    assert.equal(first.businessEligibility, 'conflict')
  }
  if (scenario.scenarioCode === 'CANARY_B') assert.equal(first.businessEligibility, 'already_exists')
  if (scenario.scenarioCode === 'CANARY_I') assert.equal(first.candidate.sourceKey, scenario.normalizationPeerSourceKey)
  results.push({
    scenarioCode: scenario.scenarioCode, candidateId: first.candidate.candidateId, sourceKey: first.candidate.sourceKey,
    evidenceStatus: first.evidenceStatus, businessEligibility: first.businessEligibility,
    runtimeExecutionAllowed: first.runtimeExecutionAllowed, targetExistenceStatus: first.targetExistenceStatus,
    targetCount: first.targetCount, targetNos: first.targetNos, blockingReasonCodes: first.candidate.blockingReasonCodes,
    ruleCount: first.rules.length, inputUnchanged: JSON.stringify(scenario) === snapshot, deterministic: JSON.stringify(first) === JSON.stringify(second), result: 'passed',
  })
}

const a = results.find((item) => item.scenarioCode === 'CANARY_A')
const j = results.find((item) => item.scenarioCode === 'CANARY_J')
assert.equal(a.candidateId, j.candidateId)
assert.equal(a.sourceKey, j.sourceKey)
assert.equal(a.ruleCount, j.ruleCount)
const report = { version: 'V1.14.2.8.4.7.36', batchId, pureFunctionCaseCount: scenarios.length, matrixCaseCount: results.length, ruleCount: purchaseReconciliationPrecheckRuleCodes.length, scenarioResults: results, formalNumberAllocationCount: 0, purchaseReconciliationWriteCount: 0, paymentObjectWriteCount: 0, result: 'passed' }
const output = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-precheck-matrix.json')
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
