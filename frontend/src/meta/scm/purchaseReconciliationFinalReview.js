import {
  normalizeBusinessActionGateInput, resolveBusinessActionFreshness, buildBusinessActionReviewResult,
  classifyBusinessActionArtifacts, authorizeBusinessActionExecution,
} from '../core/action-gate/businessActionGate.js'
import { stableBusinessActionGateHash, validateBusinessActionReviewIntegrity, restoreBusinessActionReview } from '../core/action-gate/businessActionGateIntegrity.js'
import { resolvePurchaseReconciliationTargetExistence } from './purchaseReconciliationCandidate.js'
import { buildPurchaseReconciliationSimulationRequest, validatePurchaseReconciliationSimulationIntegrity } from './purchaseReconciliationSimulation.js'

export const PURCHASE_RECONCILIATION_FINAL_REVIEW_VERSION = 'V1.14.2.8.4.7.38'
export const PURCHASE_RECONCILIATION_REVIEW_POLICY_VERSION = 'prc-final-review-policy-v1'
export const PURCHASE_RECONCILIATION_GENERATION_ACTION = 'purchase_reconciliation_generation'

export const purchaseReconciliationFinalConditionDefinitions = [
  ['PRC_FINAL_PREVIOUS_CHECKPOINT_VALID', '前置检查点', '上一正式检查点有效', 'previousCheckpointValid'],
  ['PRC_FINAL_CANDIDATE_PRESENT', '候选对象', '候选对象存在', 'candidatePresent'],
  ['PRC_FINAL_CANDIDATE_ID_MATCH', '候选对象', '候选标识一致', 'candidateIdMatch'],
  ['PRC_FINAL_SOURCE_KEY_MATCH', '候选对象', '来源键一致', 'sourceKeyMatch'],
  ['PRC_FINAL_SIMULATION_REQUEST_PRESENT', '模拟请求', '模拟请求存在', 'simulationRequestPresent'],
  ['PRC_FINAL_SIMULATION_RESULT_PRESENT', '模拟结果', '模拟结果存在', 'simulationResultPresent'],
  ['PRC_FINAL_SIMULATION_SUCCEEDED', '模拟结果', '模拟执行成功', 'simulationSucceeded'],
  ['PRC_FINAL_SIMULATION_TERMINAL', '模拟结果', '模拟结果处于终态', 'simulationTerminal'],
  ['PRC_FINAL_SIMULATION_INTEGRITY_VALID', '结果完整性', '模拟结果完整性有效', 'simulationIntegrityValid'],
  ['PRC_FINAL_SIMULATION_RESULT_IMMUTABLE', '结果完整性', '模拟结果不可变', 'simulationResultImmutable'],
  ['PRC_FINAL_PROPOSED_SNAPSHOT_PRESENT', '模拟结果', '拟生成快照存在', 'proposedSnapshotPresent'],
  ['PRC_FINAL_SOURCE_SNAPSHOT_UNCHANGED', '来源新鲜度', '来源快照未变化', 'sourceSnapshotUnchanged'],
  ['PRC_FINAL_PRECHECK_HASH_MATCH', '来源新鲜度', '预检查结果哈希一致', 'precheckHashMatch'],
  ['PRC_FINAL_SUPPLIER_CONSISTENT', '主体一致性', '供应商一致', 'supplierConsistent'],
  ['PRC_FINAL_LEGAL_ENTITY_CONSISTENT', '主体一致性', '法人一致', 'legalEntityConsistent'],
  ['PRC_FINAL_LEDGER_BOOK_CONSISTENT', '主体一致性', '账套一致', 'ledgerBookConsistent'],
  ['PRC_FINAL_CURRENCY_CONSISTENT', '金额和币种', '币种一致', 'currencyConsistent'],
  ['PRC_FINAL_AMOUNT_CONSISTENT', '金额和币种', '结算金额一致', 'amountConsistent'],
  ['PRC_FINAL_NO_EXISTING_TARGET', '目标唯一性', '不存在已有目标', 'noExistingTarget'],
  ['PRC_FINAL_SINGLE_TARGET_INVARIANT', '目标唯一性', '单目标不变式', 'singleTargetInvariant'],
  ['PRC_FINAL_AUDIT_EVIDENCE_COMPLETE', '审计证据', '审计证据完整', 'auditEvidenceComplete'],
  ['PRC_FINAL_NO_FATAL_RISK', '风险', '不存在致命风险', 'noFatalRisk'],
  ['PRC_FINAL_RUNTIME_CREATION_DISABLED', '运行时保护', '正式生成权限保持关闭', 'runtimeCreationDisabled'],
  ['PRC_FINAL_ZERO_WRITE_INVARIANT', '零写入不变式', '正式业务保持零写入', 'zeroWriteInvariant'],
  ['PRC_FINAL_NO_AUTO_ADVANCE', '运行时保护', '禁止自动推进', 'noAutoAdvance'],
].map(([code, category, name, key]) => ({
  code, category, name, key, sourceField: key,
  evaluate: (context) => {
    const entry = context[key] || { passed: false, actual: undefined, expected: true }
    return { status: entry.passed ? 'passed' : 'blocked', actual: entry.actual, expected: entry.expected,
      message: entry.message || `${name}${entry.passed ? '通过' : '未通过'}`, blocking: !entry.passed }
  },
}))

export const purchaseReconciliationAuditRequirementFields = [
  'sourceCandidateId', 'sourceKey', 'sourceSupplierSettlementNo', 'simulationRequestId', 'simulationResultId',
  'simulationResultHash', 'reviewId', 'reviewHash', 'reviewPolicyVersion', 'conditionTableVersion',
  'sourceSnapshotHash', 'currentSourceSnapshotHash', 'reviewDecision', 'unmetConditions', 'riskItems',
]

export const purchaseReconciliationForbiddenAutoAdvanceActions = [
  '创建正式采购对账对象', '分配正式采购对账编号', '保存采购对账', '提交采购对账', '提交审核', '审核', '复核',
  '确认对账', '修改供应商结算状态', '生成付款对象', '生成付款凭证', '核销', '写总账', '过账', '生成银行流水', '导出付款文件',
]

const same = (left, right) => String(left ?? '') === String(right ?? '')
const numberSame = (left, right) => Math.abs(Number(left || 0) - Number(right || 0)) < 0.000001
const check = (passed, actual, expected, message = '') => ({ passed: Boolean(passed), actual, expected, message })

export function buildPurchaseReconciliationAuditRequirements(evidence = {}) {
  return purchaseReconciliationAuditRequirementFields.map((field) => ({ field, present: Boolean(evidence[field]), required: true }))
}

export function buildPurchaseReconciliationRiskItems({ simulationIntegrity, targetRace, freshnessResult, extraRisks = [] } = {}) {
  const items = [...extraRisks]
  if (!simulationIntegrity.integrityValid) items.push({ code: 'PRC_RISK_SIMULATION_INTEGRITY', severity: 'fatal', message: '模拟结果完整性无效' })
  if (targetRace.status === 'multiple_targets') items.push({ code: 'PRC_RISK_MULTIPLE_TARGETS', severity: 'fatal', message: '同一来源存在多个采购对账目标' })
  if (freshnessResult.status === 'stale') items.push({ code: 'PRC_RISK_STALE_SOURCE', severity: 'fatal', message: '模拟后关键来源已变化' })
  return items.sort((a, b) => String(a.code).localeCompare(String(b.code)))
}

export function resolvePurchaseReconciliationTargetRace(sourceKey, currentTargetEvidence = []) {
  return resolvePurchaseReconciliationTargetExistence(sourceKey, currentTargetEvidence)
}

export function buildPurchaseReconciliationFinalReviewInput(input = {}) {
  const candidate = input.candidate || {}
  const currentCandidate = input.currentCandidate || candidate
  const simulationRequest = input.simulationRequest || {}
  const simulationResult = input.simulationResult || {}
  const currentPrecheckResult = input.currentPrecheckResult || input.precheckResult || {}
  const currentSimulationRequest = buildPurchaseReconciliationSimulationRequest({ candidate: currentCandidate, precheckResult: currentPrecheckResult })
  const simulationIntegrity = validatePurchaseReconciliationSimulationIntegrity(simulationResult)
  const targetRace = resolvePurchaseReconciliationTargetRace(currentCandidate.sourceKey, input.currentTargetEvidence || [])
  const freshnessResult = resolveBusinessActionFreshness({
    sourceSnapshotHash: simulationRequest.inputSnapshotHash || '', currentSourceSnapshotHash: currentSimulationRequest.inputSnapshotHash,
    freshnessIdentityFields: ['candidateId', 'sourceKey'],
    simulationIdentity: { candidateId: simulationRequest.sourceCandidateId, sourceKey: simulationRequest.sourceKey },
    currentIdentity: { candidateId: currentCandidate.candidateId, sourceKey: currentCandidate.sourceKey },
  })
  const proposed = simulationResult.proposedPurchaseReconciliationSnapshot || {}
  const auditRequirements = buildPurchaseReconciliationAuditRequirements(input.auditEvidence || {})
  const auditComplete = auditRequirements.every((item) => item.present)
  const preliminaryRisks = buildPurchaseReconciliationRiskItems({ simulationIntegrity, targetRace, freshnessResult, extraRisks: input.extraRisks || [] })
  const fatalRisksOutsideFreshness = preliminaryRisks.filter((item) => item.severity === 'fatal' && item.code !== 'PRC_RISK_STALE_SOURCE')
  const writes = input.writeMetrics || {}
  const zeroWrite = ['formalBusinessWriteCount', 'formalNumberAllocationCount', 'purchaseReconciliationWriteCount', 'supplierSettlementWriteCount', 'paymentObjectWriteCount', 'localStorageBusinessWriteCount', 'networkWriteRequestCount'].every((key) => Number(writes[key] || 0) === 0)
  const conditions = {
    previousCheckpointValid: check(input.previousCheckpointValid === true, input.previousCheckpointValid, true),
    candidatePresent: check(Boolean(candidate.candidateId), candidate.candidateId || '', 'non-empty'),
    candidateIdMatch: check(same(simulationRequest.sourceCandidateId, candidate.candidateId), simulationRequest.sourceCandidateId, candidate.candidateId),
    sourceKeyMatch: check(same(simulationRequest.sourceKey, candidate.sourceKey), simulationRequest.sourceKey, candidate.sourceKey),
    simulationRequestPresent: check(Boolean(simulationRequest.simulationRequestId), simulationRequest.simulationRequestId || '', 'non-empty'),
    simulationResultPresent: check(Boolean(simulationResult.simulationResultId), simulationResult.simulationResultId || '', 'non-empty'),
    simulationSucceeded: check(simulationResult.finalState === 'simulation_succeeded', simulationResult.finalState, 'simulation_succeeded'),
    simulationTerminal: check(simulationResult.terminal === true, simulationResult.terminal, true),
    simulationIntegrityValid: check(simulationIntegrity.integrityValid, simulationIntegrity.actualResultHash, simulationIntegrity.expectedResultHash),
    simulationResultImmutable: check(simulationIntegrity.integrityValid, simulationIntegrity.integrityValid, true),
    proposedSnapshotPresent: check(Boolean(simulationResult.proposedPurchaseReconciliationSnapshot), Boolean(simulationResult.proposedPurchaseReconciliationSnapshot), true),
    sourceSnapshotUnchanged: check(freshnessResult.status === 'fresh', freshnessResult.currentSourceSnapshotHash, freshnessResult.sourceSnapshotHash),
    precheckHashMatch: check(same(simulationRequest.precheckResultHash, currentSimulationRequest.precheckResultHash), currentSimulationRequest.precheckResultHash, simulationRequest.precheckResultHash),
    supplierConsistent: check(same(proposed.supplierId, currentCandidate.supplierId), currentCandidate.supplierId, proposed.supplierId),
    legalEntityConsistent: check(same(proposed.legalEntityId, currentCandidate.legalEntityId), currentCandidate.legalEntityId, proposed.legalEntityId),
    ledgerBookConsistent: check(same(proposed.ledgerBookId, currentCandidate.ledgerBookId), currentCandidate.ledgerBookId, proposed.ledgerBookId),
    currencyConsistent: check(same(proposed.currency, currentCandidate.currency), currentCandidate.currency, proposed.currency),
    amountConsistent: check(numberSame(proposed.settlementAmount, currentCandidate.amount), currentCandidate.amount, proposed.settlementAmount),
    noExistingTarget: check(targetRace.status === 'not_found', targetRace.targetCount, 0),
    singleTargetInvariant: check(targetRace.targetCount <= 1, targetRace.targetCount, '<= 1'),
    auditEvidenceComplete: check(auditComplete, auditRequirements.filter((item) => !item.present).map((item) => item.field), []),
    noFatalRisk: check(fatalRisksOutsideFreshness.length === 0, fatalRisksOutsideFreshness.map((item) => item.code), []),
    runtimeCreationDisabled: check(input.runtimeFormalCreationAllowed !== true, false, false),
    zeroWriteInvariant: check(zeroWrite, writes, 'all zero'),
    noAutoAdvance: check(input.autoAdvanceAttempted !== true, Boolean(input.autoAdvanceAttempted), false),
  }
  const conditionInputs = {
    previousCheckpointValid: input.previousCheckpointValid, candidateId: candidate.candidateId, sourceKey: candidate.sourceKey,
    simulationRequestId: simulationRequest.simulationRequestId, simulationResultId: simulationResult.simulationResultId,
    simulationResultHash: simulationResult.resultHash, sourceSnapshotHash: simulationRequest.inputSnapshotHash,
    currentSourceSnapshotHash: currentSimulationRequest.inputSnapshotHash, currentPrecheckResultHash: currentSimulationRequest.precheckResultHash,
    targetRace, auditRequirements, riskItems: preliminaryRisks, conditions,
  }
  const normalizedInput = normalizeBusinessActionGateInput({
    reviewPolicyVersion: PURCHASE_RECONCILIATION_REVIEW_POLICY_VERSION, actionCode: PURCHASE_RECONCILIATION_GENERATION_ACTION,
    sourceIdentity: { sourceCandidateId: candidate.candidateId, sourceKey: candidate.sourceKey, sourceSupplierSettlementNo: candidate.sourceSupplierSettlementNo },
    sourceSnapshotHash: simulationRequest.inputSnapshotHash, currentSourceSnapshotHash: currentSimulationRequest.inputSnapshotHash,
    conditionInputs, auditRequirements, riskItems: preliminaryRisks, formalBusinessWriteCount: Number(writes.formalBusinessWriteCount || 0),
    failureInjectionCode: input.failureInjectionCode || '',
  })
  return { candidate, currentCandidate, simulationRequest, simulationResult, currentSimulationRequest, simulationIntegrity, targetRace, freshnessResult, auditRequirements, riskItems: preliminaryRisks, conditions, writes, normalizedInput }
}

export function evaluatePurchaseReconciliationFinalConditions(input = {}) {
  return buildPurchaseReconciliationFinalReviewInput(input)
}

export function buildPurchaseReconciliationFinalReview(input = {}) {
  const context = buildPurchaseReconciliationFinalReviewInput(input)
  const generic = buildBusinessActionReviewResult({
    normalizedInput: context.normalizedInput, conditionDefinitions: purchaseReconciliationFinalConditionDefinitions,
    conditionContext: context.conditions, freshnessResult: context.freshnessResult, failureInjectionCode: input.failureInjectionCode || '',
  })
  const enriched = {
    ...generic, sourceCandidateId: context.candidate.candidateId, sourceKey: context.candidate.sourceKey,
    sourceSupplierSettlementNo: context.candidate.sourceSupplierSettlementNo,
    simulationRequestId: context.simulationRequest.simulationRequestId, simulationResultId: context.simulationResult.simulationResultId,
    simulationResultHash: context.simulationResult.resultHash, sourceSnapshotHash: context.simulationRequest.inputSnapshotHash,
    currentSourceSnapshotHash: context.currentSimulationRequest.inputSnapshotHash,
    precheckResultHash: context.simulationRequest.precheckResultHash,
    integrityResult: context.simulationIntegrity.integrityValid ? 'valid' : 'invalid',
    simulationFinalState: context.simulationResult.finalState || '',
    simulationAmount: context.simulationResult.proposedPurchaseReconciliationSnapshot?.settlementAmount ?? null,
    currentAmount: context.currentCandidate.amount ?? null,
    amountDifference: Number(context.currentCandidate.amount || 0) - Number(context.simulationResult.proposedPurchaseReconciliationSnapshot?.settlementAmount || 0),
    simulationCurrency: context.simulationResult.proposedPurchaseReconciliationSnapshot?.currency || '',
    currentCurrency: context.currentCandidate.currency || '',
    targetExistenceStatus: context.targetRace.status, existingTargetNos: context.targetRace.targetNos,
    currentTargetCount: context.targetRace.targetCount, runtimeFormalCreationAllowed: false,
    artifactClassification: classifyBusinessActionArtifacts(input.artifactClassification || {}),
    formalNumberAllocationCount: 0, purchaseReconciliationWriteCount: 0, supplierSettlementWriteCount: 0,
    paymentObjectWriteCount: 0, localStorageBusinessWriteCount: 0, networkWriteRequestCount: 0,
    forbiddenAutoAdvanceActions: purchaseReconciliationForbiddenAutoAdvanceActions,
  }
  const { reviewHash, resultSource, artifactClassification, ...hashPayload } = enriched
  return { ...hashPayload, artifactClassification, resultSource, reviewHash: stableBusinessActionGateHash(hashPayload) }
}

export function validatePurchaseReconciliationFinalReviewIntegrity(review = {}) {
  return validateBusinessActionReviewIntegrity(review)
}

export function restorePurchaseReconciliationFinalReview(review = {}) {
  return restoreBusinessActionReview(review)
}

export function authorizePurchaseReconciliationFormalGeneration(review = {}) {
  return authorizeBusinessActionExecution({ review, requestedActionCode: PURCHASE_RECONCILIATION_GENERATION_ACTION })
}
