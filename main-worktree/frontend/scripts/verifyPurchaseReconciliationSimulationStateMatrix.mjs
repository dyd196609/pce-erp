import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import {
  purchaseReconciliationSimulationStates,
  purchaseReconciliationSimulationEvents,
  purchaseReconciliationSimulationAllowedTransitions,
  purchaseReconciliationSimulationTerminalStates,
  buildPurchaseReconciliationSimulationRequest,
  buildPurchaseReconciliationSimulationResult,
  restorePurchaseReconciliationSimulationResult,
  transitionPurchaseReconciliationSimulationState,
} from '../src/meta/scm/purchaseReconciliationSimulation.js'
import {
  buildPurchaseReconciliationSimulationCanaryScenarios,
  buildPurchaseReconciliationSimulationScenarioArtifacts,
} from '../tests/helpers/purchaseReconciliationSimulationCanaryFixtures.js'

const batchId = process.env.PCE_CANARY_BATCH_ID || 'prc-simulation-matrix-stable'
const scenarios = buildPurchaseReconciliationSimulationCanaryScenarios(batchId)
assert.equal(scenarios.length, 11)
assert.equal(new Set(purchaseReconciliationSimulationStates).size, 7)
assert.equal(new Set(purchaseReconciliationSimulationEvents).size, 9)
assert.equal(Object.keys(purchaseReconciliationSimulationAllowedTransitions).length, 6)
assert.deepEqual(purchaseReconciliationSimulationTerminalStates, ['precheck_blocked', 'simulation_succeeded', 'simulation_failed'])

const rows = scenarios.map((scenario) => {
  const inputBefore = JSON.stringify(scenario)
  const artifacts = buildPurchaseReconciliationSimulationScenarioArtifacts(scenario)
  const repeatedRequest = buildPurchaseReconciliationSimulationRequest({ candidate: artifacts.precheck.candidate, precheckResult: artifacts.precheck })
  const repeatedResult = buildPurchaseReconciliationSimulationResult({ request: repeatedRequest, candidate: artifacts.precheck.candidate, precheckResult: artifacts.precheck, origin: scenario.origin, failureInjectionCode: scenario.failureInjectionCode })
  assert.equal(JSON.stringify(scenario), inputBefore)
  assert.deepEqual(repeatedRequest, artifacts.request)
  assert.deepEqual(repeatedResult, artifacts.result)
  assert.equal(artifacts.result.formalCreationAllowed, false)
  assert.equal(artifacts.result.formalNumberAllocated, false)
  assert.equal(artifacts.result.formalPurchaseReconciliationWriteCount, 0)
  assert.equal(artifacts.result.supplierSettlementWriteCount, 0)
  assert.equal(artifacts.result.paymentObjectWriteCount, 0)
  assert.equal(artifacts.result.localStorageBusinessWriteCount, 0)
  assert.equal(artifacts.result.networkWriteRequestCount, 0)
  assert.deepEqual(artifacts.result.stateHistory.map((item) => item.sequence), artifacts.result.stateHistory.map((_, index) => index + 1))
  if (scenario.testKind === 'illegal_transition') {
    assert.equal(artifacts.illegalTransition.transitionResult, 'blocked')
    assert.equal(artifacts.illegalTransition.currentState, 'not_created')
    assert.equal(artifacts.illegalTransition.illegalTransitionCode, 'PRC_SIMULATION_ILLEGAL_TRANSITION')
  } else {
    assert.equal(artifacts.result.finalState, scenario.expectedFinalState)
    assert.equal(artifacts.result.outcome, scenario.expectedOutcome)
    assert.equal(artifacts.result.terminal, scenario.expectedTerminal)
  }
  if (scenario.testKind === 'integrity_tamper') assert.deepEqual(artifacts.integrity, { integrityValid: false, expectedResultHash: artifacts.integrity.expectedResultHash, actualResultHash: artifacts.result.resultHash, errorCode: 'PRC_SIMULATION_RESULT_INTEGRITY_FAILED' })
  else assert.equal(artifacts.integrity.integrityValid, true)
  if (artifacts.result.outcome === 'succeeded') {
    assert.ok(artifacts.result.proposedPurchaseReconciliationSnapshot)
    assert.equal(artifacts.result.proposedPurchaseReconciliationSnapshot.formalPurchaseReconciliationNo, null)
  } else assert.equal(artifacts.result.proposedPurchaseReconciliationSnapshot, null)
  return {
    scenarioCode: scenario.scenarioCode, purpose: scenario.purpose,
    simulationRequestId: artifacts.request.simulationRequestId, simulationResultId: artifacts.result.simulationResultId,
    inputSnapshotHash: artifacts.request.inputSnapshotHash, precheckResultHash: artifacts.request.precheckResultHash,
    finalState: scenario.testKind === 'illegal_transition' ? artifacts.illegalTransition.currentState : artifacts.result.finalState,
    outcome: scenario.testKind === 'illegal_transition' ? 'blocked' : artifacts.result.outcome,
    integrityValid: artifacts.integrity.integrityValid, formalBusinessWriteCount: 0, result: 'passed',
  }
})

const byCode = Object.fromEntries(rows.map((row) => [row.scenarioCode, row]))
assert.equal(byCode.CANARY_A.simulationRequestId, byCode.CANARY_F.simulationRequestId)
assert.equal(byCode.CANARY_A.simulationResultId, byCode.CANARY_F.simulationResultId)
assert.equal(byCode.CANARY_A.simulationRequestId, byCode.CANARY_J.simulationRequestId)
assert.notEqual(byCode.CANARY_A.inputSnapshotHash, byCode.CANARY_G.inputSnapshotHash)
assert.notEqual(byCode.CANARY_A.simulationRequestId, byCode.CANARY_G.simulationRequestId)
assert.equal(byCode.CANARY_E.simulationRequestId, byCode.CANARY_K.simulationRequestId)

const aArtifacts = buildPurchaseReconciliationSimulationScenarioArtifacts(scenarios[0])
const restored = restorePurchaseReconciliationSimulationResult(aArtifacts.result)
assert.equal(restored.restored, true)
assert.equal(restored.result.resultSource, 'existing_simulation_result')
const illegalExamples = [
  ['not_created', 'PRC_SIMULATION_STARTED'], ['not_created', 'PRC_SIMULATION_SUCCEEDED'],
  ['precheck_blocked', 'PRC_SIMULATION_MARKED_READY'], ['simulation_succeeded', 'PRC_SIMULATION_STARTED'],
  ['simulation_failed', 'PRC_SIMULATION_SUCCEEDED'], ['simulation_ready', 'PRC_SIMULATION_SUCCEEDED'],
]
for (const [currentState, eventCode] of illegalExamples) {
  const transition = transitionPurchaseReconciliationSimulationState({ currentState, eventCode })
  assert.equal(transition.transitionResult, 'blocked')
  assert.equal(transition.currentState, currentState)
}

const report = {
  version: 'V1.14.2.8.4.7.37', canaryBatchId: batchId,
  pureFunctionCaseCount: 18, matrixCaseCount: rows.length,
  stateCount: purchaseReconciliationSimulationStates.length, eventCount: purchaseReconciliationSimulationEvents.length,
  allowedTransitionCount: Object.keys(purchaseReconciliationSimulationAllowedTransitions).length,
  illegalTransitionCaseCount: illegalExamples.length + 1, rows,
  requestIdStability: 'passed', resultIdStability: 'passed', resultHashStability: 'passed',
  inputImmutability: 'passed', idempotency: 'passed', integrityValidation: 'passed', zeroFormalBusinessWrite: true, result: 'passed',
}
const output = path.resolve('test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-simulation-state-matrix.json')
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
