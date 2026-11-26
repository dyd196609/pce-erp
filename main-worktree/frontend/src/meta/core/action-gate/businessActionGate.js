import { businessActionConditionStatuses } from './businessActionGateStates.js'
import { cloneBusinessActionGateValue, stableBusinessActionGateHash } from './businessActionGateIntegrity.js'

const text = (value) => String(value ?? '').trim()

export function normalizeBusinessActionGateInput(input = {}) {
  return cloneBusinessActionGateValue({
    reviewPolicyVersion: text(input.reviewPolicyVersion), actionCode: text(input.actionCode),
    sourceIdentity: input.sourceIdentity || {}, sourceSnapshotHash: text(input.sourceSnapshotHash),
    currentSourceSnapshotHash: text(input.currentSourceSnapshotHash), conditionInputs: input.conditionInputs || {},
    auditRequirements: input.auditRequirements || [], riskItems: input.riskItems || [],
    formalBusinessWriteCount: Number(input.formalBusinessWriteCount || 0), failureInjectionCode: text(input.failureInjectionCode),
  })
}

export function resolveBusinessActionFreshness(input = {}) {
  const changedFields = []
  if (input.sourceSnapshotHash !== input.currentSourceSnapshotHash) changedFields.push('sourceSnapshotHash')
  for (const field of input.freshnessIdentityFields || []) {
    if (text(input.simulationIdentity?.[field]) !== text(input.currentIdentity?.[field])) changedFields.push(field)
  }
  return {
    status: changedFields.length ? 'stale' : 'fresh', sourceSnapshotHash: input.sourceSnapshotHash || '',
    currentSourceSnapshotHash: input.currentSourceSnapshotHash || '', changedFields,
  }
}

export function buildBusinessActionReviewId({ reviewPolicyVersion, actionCode, reviewInputHash } = {}) {
  const key = [reviewPolicyVersion, actionCode, reviewInputHash].map(text).join('::')
  return key.replaceAll('::', '') ? `BAR-${stableBusinessActionGateHash(key)}` : ''
}

export function evaluateBusinessActionConditions(conditionDefinitions = [], context = {}) {
  return conditionDefinitions.map((definition) => {
    const evaluation = definition.evaluate(context) || {}
    const status = businessActionConditionStatuses.includes(evaluation.status) ? evaluation.status : evaluation.passed ? 'passed' : 'blocked'
    return {
      code: definition.code, name: definition.name, category: definition.category, status,
      severity: evaluation.severity || definition.severity || 'error', actual: evaluation.actual,
      expected: evaluation.expected, message: evaluation.message || definition.message || '',
      sourceField: definition.sourceField || '', blocking: evaluation.blocking ?? (status === 'blocked'),
    }
  })
}

export function buildBusinessActionReviewResult({ normalizedInput, conditionDefinitions, conditionContext, freshnessResult, failureInjectionCode = '' } = {}) {
  const conditionResults = evaluateBusinessActionConditions(conditionDefinitions, conditionContext)
  const unmetConditions = conditionResults.filter((item) => item.blocking && item.status === 'blocked')
  let reviewState = 'review_passed'
  let reviewDecision = 'approved'
  if (failureInjectionCode) { reviewState = 'review_failed'; reviewDecision = 'failed' }
  else if (freshnessResult.status === 'stale') { reviewState = 'review_stale'; reviewDecision = 'stale' }
  else if (unmetConditions.length) { reviewState = 'review_blocked'; reviewDecision = 'blocked' }
  const reviewInputHash = stableBusinessActionGateHash(normalizedInput)
  const reviewId = buildBusinessActionReviewId({ reviewPolicyVersion: normalizedInput.reviewPolicyVersion, actionCode: normalizedInput.actionCode, reviewInputHash })
  const base = {
    reviewId, reviewPolicyVersion: normalizedInput.reviewPolicyVersion, actionCode: normalizedInput.actionCode,
    reviewInputHash, reviewState, reviewDecision,
    generationReadiness: reviewDecision === 'approved' ? 'ready' : 'not_ready', runtimeFormalCreationAllowed: false,
    conditionResults, unmetConditions, riskItems: cloneBusinessActionGateValue(normalizedInput.riskItems),
    auditRequirements: cloneBusinessActionGateValue(normalizedInput.auditRequirements), freshnessResult,
    formalBusinessWriteCount: normalizedInput.formalBusinessWriteCount, resultSource: 'new_review_result',
  }
  return { ...base, reviewHash: stableBusinessActionGateHash(base) }
}

export function classifyBusinessActionArtifacts(artifacts = {}) {
  return {
    simulationRequestArtifactCount: Number(artifacts.simulationRequestArtifactCount || 0),
    simulationResultArtifactCount: Number(artifacts.simulationResultArtifactCount || 0),
    simulationStateCheckpointCount: Number(artifacts.simulationStateCheckpointCount || 0),
    reviewArtifactCount: Number(artifacts.reviewArtifactCount || 0),
    crossProcessRecoveryCopyCount: Number(artifacts.crossProcessRecoveryCopyCount || 0),
    idempotentReuseCount: Number(artifacts.idempotentReuseCount || 0),
    rejectedIntegrityCopyCount: Number(artifacts.rejectedIntegrityCopyCount || 0),
    formalBusinessWriteCount: Number(artifacts.formalBusinessWriteCount || 0),
  }
}

export function authorizeBusinessActionExecution({ review, requestedActionCode } = {}) {
  return {
    allowed: false, requestedActionCode: text(requestedActionCode), reviewDecision: review?.reviewDecision || '',
    runtimeFormalCreationAllowed: false, errorCode: 'BUSINESS_ACTION_FORMAL_EXECUTION_DISABLED',
    formalBusinessWriteCount: 0, formalNumberAllocationCount: 0,
  }
}
