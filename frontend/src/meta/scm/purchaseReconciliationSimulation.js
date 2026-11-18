import { cloneBusinessActionGateValue, stableBusinessActionGateHash } from '../core/action-gate/businessActionGateIntegrity.js'

export const PURCHASE_RECONCILIATION_SIMULATION_VERSION = 'V1.14.2.8.4.7.37'
export const PURCHASE_RECONCILIATION_SIMULATION_POLICY_VERSION = 'prc-simulation-policy-v1'
export const PURCHASE_RECONCILIATION_SIMULATION_OPERATION = 'simulate_purchase_reconciliation_generation'
export const PURCHASE_RECONCILIATION_SIMULATION_RUNTIME_MODE = 'canary_isolated_simulation'

export const purchaseReconciliationSimulationStates = [
  'not_created', 'precheck_pending', 'precheck_blocked', 'simulation_ready',
  'simulation_running', 'simulation_succeeded', 'simulation_failed',
]

export const purchaseReconciliationSimulationTerminalStates = [
  'precheck_blocked', 'simulation_succeeded', 'simulation_failed',
]

export const purchaseReconciliationSimulationEvents = [
  'PRC_SIM_PRECHECK_REQUESTED', 'PRC_SIM_PRECHECK_BLOCKED', 'PRC_SIMULATION_MARKED_READY',
  'PRC_SIMULATION_STARTED', 'PRC_SIMULATION_SUCCEEDED', 'PRC_SIMULATION_FAILED',
  'PRC_SIMULATION_ILLEGAL_TRANSITION', 'PRC_SIMULATION_RESULT_REUSED',
  'PRC_SIMULATION_RESULT_INTEGRITY_FAILED',
]

export const purchaseReconciliationSimulationAllowedTransitions = Object.freeze({
  'not_created::PRC_SIM_PRECHECK_REQUESTED': 'precheck_pending',
  'precheck_pending::PRC_SIM_PRECHECK_BLOCKED': 'precheck_blocked',
  'precheck_pending::PRC_SIMULATION_MARKED_READY': 'simulation_ready',
  'simulation_ready::PRC_SIMULATION_STARTED': 'simulation_running',
  'simulation_running::PRC_SIMULATION_SUCCEEDED': 'simulation_succeeded',
  'simulation_running::PRC_SIMULATION_FAILED': 'simulation_failed',
})

const clone = cloneBusinessActionGateValue
const text = (value) => String(value ?? '').trim()

export function stablePurchaseReconciliationSimulationHash(value) {
  return stableBusinessActionGateHash(value)
}

function businessSnapshot(candidate = {}, precheck = {}) {
  return {
    sourceCandidateId: text(candidate.candidateId), sourceKey: text(candidate.sourceKey),
    sourceSupplierSettlementNo: text(candidate.sourceSupplierSettlementNo),
    supplierId: text(candidate.supplierId), supplierName: text(candidate.supplierName),
    legalEntityId: text(candidate.legalEntityId), ledgerBookId: text(candidate.ledgerBookId),
    currency: text(candidate.currency).toUpperCase(), exchangeRate: Number(candidate.exchangeRate || 0),
    quantity: Number(candidate.quantity || 0), unit: text(candidate.unit), settlementAmount: Number(candidate.amount || 0),
    sourcePayableCheckNo: text(candidate.sourcePayableCheckNo), sourcePayablePrepareNo: text(candidate.sourcePayablePrepareNo),
    purchaseOrderNo: text(candidate.purchaseOrderNo), priceApprovalNo: text(candidate.priceApprovalNo),
    receiptNo: text(candidate.receiptNo), inspectionNo: text(candidate.inspectionNo),
    warehouseTaskNo: text(candidate.warehouseTaskNo), inventoryTransactionNo: text(candidate.inventoryTransactionNo),
    businessEligibility: text(precheck.businessEligibility), targetExistenceStatus: text(precheck.targetExistenceStatus),
    targetCount: Number(precheck.targetCount || 0), targetNos: clone(precheck.targetNos || []),
  }
}

export function buildPurchaseReconciliationSimulationRequestId(input = {}) {
  const key = [input.simulationPolicyVersion, input.sourceCandidateId, input.inputSnapshotHash, input.precheckResultHash].map(text).join('::')
  return key.replaceAll('::', '') ? `PRC-SIM-REQ-${stablePurchaseReconciliationSimulationHash(key)}` : ''
}

export function buildPurchaseReconciliationSimulationRequest({ candidate = {}, precheckResult = {}, simulationPolicyVersion = PURCHASE_RECONCILIATION_SIMULATION_POLICY_VERSION } = {}) {
  const inputSnapshot = businessSnapshot(candidate, precheckResult)
  const inputSnapshotHash = stablePurchaseReconciliationSimulationHash(inputSnapshot)
  const precheckResultHash = stablePurchaseReconciliationSimulationHash({
    evidenceStatus: precheckResult.evidenceStatus, businessEligibility: precheckResult.businessEligibility,
    targetExistenceStatus: precheckResult.targetExistenceStatus, targetCount: precheckResult.targetCount,
    targetNos: precheckResult.targetNos || [], rules: (precheckResult.rules || []).map(({ code, status, actual, expected }) => ({ code, status, actual, expected })),
  })
  const base = {
    simulationPolicyVersion, sourceCandidateId: text(candidate.candidateId), sourceKey: text(candidate.sourceKey),
    sourceSupplierSettlementNo: text(candidate.sourceSupplierSettlementNo), inputSnapshotHash, precheckResultHash,
    requestedOperation: PURCHASE_RECONCILIATION_SIMULATION_OPERATION,
    runtimeMode: PURCHASE_RECONCILIATION_SIMULATION_RUNTIME_MODE, formalCreationAllowed: false,
  }
  const simulationRequestId = buildPurchaseReconciliationSimulationRequestId(base)
  return { ...base, simulationRequestId, requestUniquenessKey: simulationRequestId, inputSnapshot }
}

export function evaluatePurchaseReconciliationSimulationAuthorization({ precheckResult = {}, runtimeMode = PURCHASE_RECONCILIATION_SIMULATION_RUNTIME_MODE, origin = 'canary' } = {}) {
  const businessEligibility = text(precheckResult.businessEligibility)
  const blockedRules = (precheckResult.rules || []).filter((item) => item.status === 'blocked')
  const simulationExecutionAllowed = businessEligibility === 'eligible'
    && runtimeMode === PURCHASE_RECONCILIATION_SIMULATION_RUNTIME_MODE
    && origin === 'canary'
    && blockedRules.length === 0
  return { businessEligibility, simulationExecutionAllowed, formalCreationAllowed: false,
    reasonCodes: simulationExecutionAllowed ? [] : [...new Set(blockedRules.map((item) => item.code).concat(businessEligibility === 'eligible' ? [] : [`PRC_SIM_ELIGIBILITY_${businessEligibility.toUpperCase() || 'UNKNOWN'}`]))] }
}

export function transitionPurchaseReconciliationSimulationState({ currentState = 'not_created', eventCode, stateHistory = [], reasonCode = '' } = {}) {
  const history = clone(stateHistory || [])
  const toState = purchaseReconciliationSimulationAllowedTransitions[`${currentState}::${eventCode}`]
  if (!toState || purchaseReconciliationSimulationTerminalStates.includes(currentState)) {
    return {
      transitionResult: 'blocked', currentState, illegalTransitionCode: 'PRC_SIMULATION_ILLEGAL_TRANSITION',
      stateHistory: history.concat({ sequence: history.length + 1, fromState: currentState, eventCode: 'PRC_SIMULATION_ILLEGAL_TRANSITION', toState: currentState, reasonCode: reasonCode || `${currentState}::${eventCode}`, terminal: purchaseReconciliationSimulationTerminalStates.includes(currentState) }),
    }
  }
  return { transitionResult: 'transitioned', currentState: toState, illegalTransitionCode: '',
    stateHistory: history.concat({ sequence: history.length + 1, fromState: currentState, eventCode, toState, reasonCode, terminal: purchaseReconciliationSimulationTerminalStates.includes(toState) }) }
}

export function buildProposedPurchaseReconciliationSnapshot(candidate = {}) {
  return {
    sourceCandidateId: text(candidate.candidateId), sourceKey: text(candidate.sourceKey),
    sourceSupplierSettlementNo: text(candidate.sourceSupplierSettlementNo), supplierId: text(candidate.supplierId), supplierName: text(candidate.supplierName),
    legalEntityId: text(candidate.legalEntityId), ledgerBookId: text(candidate.ledgerBookId), currency: text(candidate.currency),
    exchangeRate: Number(candidate.exchangeRate || 0), quantity: Number(candidate.quantity || 0), unit: text(candidate.unit), settlementAmount: Number(candidate.amount || 0),
    sourcePayableCheckNo: text(candidate.sourcePayableCheckNo), sourcePayablePrepareNo: text(candidate.sourcePayablePrepareNo),
    purchaseOrderNo: text(candidate.purchaseOrderNo), priceApprovalNo: text(candidate.priceApprovalNo), receiptNo: text(candidate.receiptNo),
    inspectionNo: text(candidate.inspectionNo), warehouseTaskNo: text(candidate.warehouseTaskNo), inventoryTransactionNo: text(candidate.inventoryTransactionNo),
    formalPurchaseReconciliationNo: null,
  }
}

function resultHashPayload(result) {
  const { resultHash, resultSource, integrityValid, integrityErrorCode, ...payload } = result
  return payload
}

export function buildPurchaseReconciliationSimulationResultHash(result = {}) {
  return stablePurchaseReconciliationSimulationHash(resultHashPayload(result))
}

export function buildPurchaseReconciliationSimulationResult({ request = {}, candidate = {}, precheckResult = {}, origin = 'canary', failureInjectionCode = '' } = {}) {
  const authorization = evaluatePurchaseReconciliationSimulationAuthorization({ precheckResult, runtimeMode: request.runtimeMode, origin })
  let currentState = 'not_created'
  let stateHistory = []
  const apply = (eventCode, reasonCode = '') => {
    const transition = transitionPurchaseReconciliationSimulationState({ currentState, eventCode, stateHistory, reasonCode })
    currentState = transition.currentState
    stateHistory = transition.stateHistory
  }
  apply('PRC_SIM_PRECHECK_REQUESTED')
  if (!authorization.simulationExecutionAllowed) apply('PRC_SIM_PRECHECK_BLOCKED', authorization.reasonCodes[0] || 'PRC_SIM_PRECHECK_BLOCKED')
  else {
    apply('PRC_SIMULATION_MARKED_READY')
    apply('PRC_SIMULATION_STARTED')
    if (failureInjectionCode === 'PRC_SIM_TEST_FAILURE' && origin === 'canary') apply('PRC_SIMULATION_FAILED', failureInjectionCode)
    else apply('PRC_SIMULATION_SUCCEEDED')
  }
  const outcome = currentState === 'simulation_succeeded' ? 'succeeded' : currentState === 'simulation_failed' ? 'failed' : 'blocked'
  const proposedPurchaseReconciliationSnapshot = outcome === 'succeeded' ? buildProposedPurchaseReconciliationSnapshot(candidate) : null
  const base = {
    simulationRequestId: request.simulationRequestId, sourceCandidateId: request.sourceCandidateId, sourceKey: request.sourceKey,
    initialState: 'not_created', finalState: currentState, outcome, terminal: purchaseReconciliationSimulationTerminalStates.includes(currentState),
    precheckResult: { evidenceStatus: precheckResult.evidenceStatus, businessEligibility: precheckResult.businessEligibility, targetExistenceStatus: precheckResult.targetExistenceStatus, targetCount: precheckResult.targetCount, targetNos: clone(precheckResult.targetNos || []) },
    stateHistory, proposedPurchaseReconciliationSnapshot,
    blockingReasonCodes: outcome === 'blocked' ? authorization.reasonCodes : [],
    failureReasonCodes: outcome === 'failed' ? [failureInjectionCode || 'PRC_SIMULATION_CONTROLLED_FAILURE'] : [], warningCodes: [],
    formalNumberAllocated: false, formalPurchaseReconciliationWriteCount: 0, supplierSettlementWriteCount: 0,
    paymentObjectWriteCount: 0, localStorageBusinessWriteCount: 0, networkWriteRequestCount: 0,
    formalCreationAllowed: false, simulationExecutionAllowed: authorization.simulationExecutionAllowed,
  }
  const simulationResultId = `PRC-SIM-RES-${stablePurchaseReconciliationSimulationHash({ requestId: request.simulationRequestId, finalState: currentState, outcome })}`
  const withId = { ...base, simulationResultId, resultSource: 'new_simulation_result' }
  return { ...withId, resultHash: buildPurchaseReconciliationSimulationResultHash(withId) }
}

export function validatePurchaseReconciliationSimulationIntegrity(result = {}) {
  const expectedResultHash = buildPurchaseReconciliationSimulationResultHash(result)
  const integrityValid = Boolean(result.resultHash) && result.resultHash === expectedResultHash
  return { integrityValid, expectedResultHash, actualResultHash: result.resultHash || '', errorCode: integrityValid ? '' : 'PRC_SIMULATION_RESULT_INTEGRITY_FAILED' }
}

export function restorePurchaseReconciliationSimulationResult(result = {}) {
  const restored = clone(result)
  const integrity = validatePurchaseReconciliationSimulationIntegrity(restored)
  if (!integrity.integrityValid) return { restored: false, result: null, ...integrity }
  return { restored: true, result: { ...restored, resultSource: 'existing_simulation_result', integrityValid: true }, ...integrity }
}
