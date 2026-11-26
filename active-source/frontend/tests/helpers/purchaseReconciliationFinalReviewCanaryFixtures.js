import { buildPurchaseReconciliationPrecheckResult } from '../../src/meta/scm/purchaseReconciliationCandidate.js'
import { buildPurchaseReconciliationSimulationCanaryScenarios, buildPurchaseReconciliationSimulationScenarioArtifacts } from './purchaseReconciliationSimulationCanaryFixtures.js'
import { buildPurchaseReconciliationFinalReview, purchaseReconciliationAuditRequirementFields } from '../../src/meta/scm/purchaseReconciliationFinalReview.js'

function auditEvidence(overrides = {}) {
  return Object.fromEntries(purchaseReconciliationAuditRequirementFields.map((field) => [field, `available:${field}`]).concat(Object.entries(overrides)))
}

function writeMetrics() {
  return { formalBusinessWriteCount: 0, formalNumberAllocationCount: 0, purchaseReconciliationWriteCount: 0, supplierSettlementWriteCount: 0, paymentObjectWriteCount: 0, localStorageBusinessWriteCount: 0, networkWriteRequestCount: 0 }
}

function buildCurrent(candidateInput) {
  const precheck = buildPurchaseReconciliationPrecheckResult(candidateInput)
  return { currentCandidate: precheck.candidate, currentPrecheckResult: precheck }
}

function makeScenario(batchId, scenarioCode, purpose, simulationScenario, overrides = {}) {
  const simulation = buildPurchaseReconciliationSimulationScenarioArtifacts(simulationScenario)
  const current = buildCurrent(simulationScenario.candidateInput)
  return {
    origin: 'canary', canaryBatchId: batchId, scenarioCode, purpose,
    simulationScenario, candidate: simulation.precheck.candidate, precheckResult: simulation.precheck,
    simulationRequest: simulation.request, simulationResult: simulation.result,
    ...current, currentTargetEvidence: [], previousCheckpointValid: true,
    auditEvidence: auditEvidence(), writeMetrics: writeMetrics(), runtimeFormalCreationAllowed: false,
    artifactClassification: { simulationRequestArtifactCount: 1, simulationResultArtifactCount: 1, simulationStateCheckpointCount: 1, reviewArtifactCount: 1, crossProcessRecoveryCopyCount: 0, idempotentReuseCount: 0, rejectedIntegrityCopyCount: 0, formalBusinessWriteCount: 0 },
    expectedRuntimeFormalCreationAllowed: false, expectedFormalBusinessWriteCount: 0, ...overrides,
  }
}

export function buildPurchaseReconciliationFinalReviewCanaries(batchId) {
  const simulationScenarios = buildPurchaseReconciliationSimulationCanaryScenarios(batchId)
  const simulationA = simulationScenarios.find((item) => item.scenarioCode === 'CANARY_A')
  const simulationBlocked = simulationScenarios.find((item) => item.scenarioCode === 'CANARY_B')
  const simulationFailed = simulationScenarios.find((item) => item.scenarioCode === 'CANARY_E')
  const a = makeScenario(batchId, 'CANARY_A', '模拟成功且最终评审通过', simulationA, { expectedReviewState: 'review_passed', expectedReviewDecision: 'approved' })
  const amountInput = JSON.parse(JSON.stringify(simulationA.candidateInput))
  amountInput.sourceSettlement.settlementAmount = 89
  amountInput.upstreamEvidence.amount = 89
  const currencyInput = JSON.parse(JSON.stringify(simulationA.candidateInput))
  currencyInput.sourceSettlement.currency = 'USD'
  currencyInput.upstreamEvidence.currency = 'USD'
  const amountCurrent = buildCurrent(amountInput)
  const currencyCurrent = buildCurrent(currencyInput)
  const gTarget = `PRC-EVIDENCE-${String(batchId).replace(/\D/g, '').slice(-10)}-G`
  const hTargets = [`PRC-EVIDENCE-${String(batchId).replace(/\D/g, '').slice(-10)}-H1`, `PRC-EVIDENCE-${String(batchId).replace(/\D/g, '').slice(-10)}-H2`]
  const kSimulationScenario = { ...simulationA, candidateInput: amountInput }
  const k = makeScenario(batchId, 'CANARY_K', '有效输入变化后重新评审', kSimulationScenario, { expectedReviewState: 'review_passed', expectedReviewDecision: 'approved', changesScenarioCode: 'CANARY_A' })
  return [
    a,
    makeScenario(batchId, 'CANARY_B', '模拟预检查阻断', simulationBlocked, { expectedReviewState: 'review_blocked', expectedReviewDecision: 'blocked', expectedBlockingCode: 'PRC_FINAL_SIMULATION_SUCCEEDED' }),
    makeScenario(batchId, 'CANARY_C', '模拟执行失败', simulationFailed, { expectedReviewState: 'review_blocked', expectedReviewDecision: 'blocked', expectedBlockingCode: 'PRC_FINAL_SIMULATION_SUCCEEDED' }),
    makeScenario(batchId, 'CANARY_D', '模拟结果完整性损坏', simulationA, { simulationResult: { ...a.simulationResult, finalState: 'simulation_failed' }, expectedReviewState: 'review_blocked', expectedReviewDecision: 'blocked', expectedBlockingCode: 'PRC_FINAL_SIMULATION_INTEGRITY_VALID', artifactClassification: { ...a.artifactClassification, rejectedIntegrityCopyCount: 1 } }),
    makeScenario(batchId, 'CANARY_E', '模拟后来源金额变化', simulationA, { ...amountCurrent, expectedReviewState: 'review_stale', expectedReviewDecision: 'stale' }),
    makeScenario(batchId, 'CANARY_F', '模拟后币种变化', simulationA, { ...currencyCurrent, expectedReviewState: 'review_stale', expectedReviewDecision: 'stale' }),
    makeScenario(batchId, 'CANARY_G', '模拟后出现一个已有目标', simulationA, { currentTargetEvidence: [{ sourceKey: a.candidate.sourceKey, targetNo: gTarget }], expectedReviewState: 'review_blocked', expectedReviewDecision: 'blocked', expectedTargetStatus: 'single_target' }),
    makeScenario(batchId, 'CANARY_H', '模拟后出现多个目标', simulationA, { currentTargetEvidence: hTargets.map((targetNo) => ({ sourceKey: a.candidate.sourceKey, targetNo })), expectedReviewState: 'review_blocked', expectedReviewDecision: 'blocked', expectedTargetStatus: 'multiple_targets' }),
    makeScenario(batchId, 'CANARY_I', '缺少必要审计证据', simulationA, { auditEvidence: auditEvidence({ simulationResultHash: '' }), expectedReviewState: 'review_blocked', expectedReviewDecision: 'blocked', expectedBlockingCode: 'PRC_FINAL_AUDIT_EVIDENCE_COMPLETE' }),
    makeScenario(batchId, 'CANARY_J', '相同输入重复最终评审', simulationA, { expectedReviewState: 'review_passed', expectedReviewDecision: 'approved', reusesScenarioCode: 'CANARY_A', artifactClassification: { ...a.artifactClassification, idempotentReuseCount: 1 } }),
    k,
    makeScenario(batchId, 'CANARY_L', '成功评审跨进程恢复', simulationA, { expectedReviewState: 'review_passed', expectedReviewDecision: 'approved', reusesScenarioCode: 'CANARY_A', artifactClassification: { ...a.artifactClassification, crossProcessRecoveryCopyCount: 1 } }),
    makeScenario(batchId, 'CANARY_M', '失效评审跨进程恢复', simulationA, { ...amountCurrent, expectedReviewState: 'review_stale', expectedReviewDecision: 'stale', reusesScenarioCode: 'CANARY_E', artifactClassification: { ...a.artifactClassification, crossProcessRecoveryCopyCount: 1 } }),
    makeScenario(batchId, 'CANARY_N', '越权调用正式生成动作', simulationA, { expectedReviewState: 'review_passed', expectedReviewDecision: 'approved', unauthorizedGenerationAttempt: true }),
    makeScenario(batchId, 'CANARY_O', '评审引擎受控失败', simulationA, { failureInjectionCode: 'PRC_FINAL_REVIEW_TEST_FAILURE', expectedReviewState: 'review_failed', expectedReviewDecision: 'failed' }),
  ]
}

export function buildPurchaseReconciliationFinalReviewScenarioArtifacts(scenario) {
  const review = buildPurchaseReconciliationFinalReview(scenario)
  return { review }
}
