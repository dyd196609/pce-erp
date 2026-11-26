import { buildPurchaseReconciliationPrecheckResult } from '../../src/meta/scm/purchaseReconciliationCandidate.js'
import {
  buildPurchaseReconciliationSimulationRequest,
  buildPurchaseReconciliationSimulationResult,
  transitionPurchaseReconciliationSimulationState,
  validatePurchaseReconciliationSimulationIntegrity,
} from '../../src/meta/scm/purchaseReconciliationSimulation.js'

function digitsFor(batchId) {
  return String(batchId).replace(/\D/g, '').padEnd(14, '0').slice(0, 14)
}

function source(batchId, code, overrides = {}) {
  const digits = digitsFor(batchId)
  const suffix = String(code.charCodeAt(0)).slice(-2)
  return {
    id: `simulation-settlement-${batchId}-${code}`, settlementNo: `SETSIM${digits}${suffix}`,
    supplierId: `SIM-SUPPLIER-${code}`, supplierName: `模拟供应商${code}`,
    legalEntityId: 'LE-SIM-001', legalEntityName: '模拟法人', ledgerBookId: 'LEDGER-SIM-001', ledgerBookName: '模拟账套',
    businessUnitId: 'BU-SIM-001', businessUnitName: '模拟业务单元', currency: 'CNY', exchangeRate: 1,
    settlementQuantity: 2, unit: '件', settlementAmount: 88, settlementStatus: 'reconciling',
    sourcePayableCheckNo: `PCSIM${digits}${suffix}`, sourcePayablePrepareNo: `PPSIM${digits}${suffix}`,
    sourcePurchaseOrderNo: `POSIM${digits}${suffix}`, sourcePriceApprovalNo: `PASIM${digits}${suffix}`,
    sourceReceiveNo: `PRVSIM${digits}${suffix}`, sourceInspectionNo: `IQCSIM${digits}${suffix}`,
    sourceWarehouseTaskNo: `WTSIM${digits}${suffix}`, sourceInventoryTransactionNos: [`TXNSIM${digits}${suffix}`],
    ...overrides,
  }
}

function candidateInput(sourceSettlement, overrides = {}) {
  return {
    sourceType: 'supplier_settlement', contextState: 'existing_settlement', sourceSettlement,
    upstreamEvidence: { supplierId: sourceSettlement.supplierId, currency: sourceSettlement.currency, amount: sourceSettlement.settlementAmount },
    targetEvidence: [], writeMetrics: { purchaseReconciliationWrites: 0, supplierSettlementStatusWrites: 0, paymentObjectWrites: 0, formalNumberAllocations: 0, localStorageWrites: 0, networkWriteRequests: 0 },
    ...overrides,
  }
}

function scenario(batchId, scenarioCode, purpose, input, overrides = {}) {
  return { origin: 'canary', canaryBatchId: batchId, scenarioCode, purpose, candidateInput: input,
    failureInjectionCode: '', testKind: 'normal', expectedFormalBusinessWriteCount: 0, ...overrides }
}

export function buildPurchaseReconciliationSimulationCanaryScenarios(batchId) {
  const aSource = source(batchId, 'A')
  const bSource = source(batchId, 'B', { sourcePriceApprovalNo: '' })
  const cSource = source(batchId, 'C')
  const cPrecheck = buildPurchaseReconciliationPrecheckResult(candidateInput(cSource))
  const dSource = source(batchId, 'D')
  const dPrecheck = buildPurchaseReconciliationPrecheckResult(candidateInput(dSource))
  const eSource = source(batchId, 'E')
  const gSource = { ...aSource, settlementAmount: 89 }
  const a = scenario(batchId, 'CANARY_A', '有效候选模拟成功', candidateInput(aSource), { expectedFinalState: 'simulation_succeeded', expectedOutcome: 'succeeded', expectedTerminal: true })
  const e = scenario(batchId, 'CANARY_E', '受控模拟失败', candidateInput(eSource), { failureInjectionCode: 'PRC_SIM_TEST_FAILURE', expectedFinalState: 'simulation_failed', expectedOutcome: 'failed', expectedTerminal: true })
  return [
    a,
    scenario(batchId, 'CANARY_B', '预检查阻断', candidateInput(bSource), { expectedFinalState: 'precheck_blocked', expectedOutcome: 'blocked', expectedTerminal: true }),
    scenario(batchId, 'CANARY_C', '已有唯一目标', candidateInput(cSource, { targetEvidence: [{ sourceKey: cPrecheck.candidate.sourceKey, targetNo: `PRCSIM${digitsFor(batchId)}21`, evidenceOnly: true }] }), { expectedFinalState: 'precheck_blocked', expectedOutcome: 'blocked', expectedTerminal: true }),
    scenario(batchId, 'CANARY_D', '同一来源存在多个目标', candidateInput(dSource, { targetEvidence: [{ sourceKey: dPrecheck.candidate.sourceKey, targetNo: `PRCSIM${digitsFor(batchId)}31`, evidenceOnly: true }, { sourceKey: dPrecheck.candidate.sourceKey, targetNo: `PRCSIM${digitsFor(batchId)}32`, evidenceOnly: true }] }), { expectedFinalState: 'precheck_blocked', expectedOutcome: 'blocked', expectedTerminal: true }),
    e,
    scenario(batchId, 'CANARY_F', '相同请求重复执行', candidateInput(aSource), { reusesScenarioCode: 'CANARY_A', expectedFinalState: 'simulation_succeeded', expectedOutcome: 'succeeded', expectedTerminal: true }),
    scenario(batchId, 'CANARY_G', '有效业务输入变化', candidateInput(gSource), { changesScenarioCode: 'CANARY_A', expectedFinalState: 'simulation_succeeded', expectedOutcome: 'succeeded', expectedTerminal: true }),
    scenario(batchId, 'CANARY_H', '非法状态转换', candidateInput(aSource), { testKind: 'illegal_transition', expectedFinalState: 'not_created', expectedOutcome: 'blocked', expectedTerminal: false }),
    scenario(batchId, 'CANARY_I', '模拟结果完整性损坏', candidateInput(aSource), { testKind: 'integrity_tamper', expectedFinalState: 'simulation_succeeded', expectedOutcome: 'succeeded', expectedTerminal: true }),
    scenario(batchId, 'CANARY_J', '成功终态跨进程恢复', candidateInput(aSource), { reusesScenarioCode: 'CANARY_A', testKind: 'success_recovery', expectedFinalState: 'simulation_succeeded', expectedOutcome: 'succeeded', expectedTerminal: true }),
    { ...e, scenarioCode: 'CANARY_K', purpose: '失败终态跨进程恢复', testKind: 'failure_recovery', reusesScenarioCode: 'CANARY_E' },
  ]
}

export function buildPurchaseReconciliationSimulationScenarioArtifacts(scenario) {
  const precheck = buildPurchaseReconciliationPrecheckResult(scenario.candidateInput)
  const request = buildPurchaseReconciliationSimulationRequest({ candidate: precheck.candidate, precheckResult: precheck })
  const result = buildPurchaseReconciliationSimulationResult({ request, candidate: precheck.candidate, precheckResult: precheck, origin: scenario.origin, failureInjectionCode: scenario.failureInjectionCode })
  const illegalTransition = scenario.testKind === 'illegal_transition'
    ? transitionPurchaseReconciliationSimulationState({ currentState: 'not_created', eventCode: 'PRC_SIMULATION_SUCCEEDED' }) : null
  const tamperedResult = scenario.testKind === 'integrity_tamper' ? { ...result, finalState: 'simulation_failed' } : null
  const integrity = validatePurchaseReconciliationSimulationIntegrity(tamperedResult || result)
  return { precheck, request, result, illegalTransition, tamperedResult, integrity }
}
