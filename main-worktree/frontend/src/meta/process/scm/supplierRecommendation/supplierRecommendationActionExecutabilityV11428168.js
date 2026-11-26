import { canPerformAction } from '../../../runtime/permissionEngine.js'
import { evaluateSupplierRecommendationActionGuardV1142811 } from './supplierRecommendationActionContractsV1142811.js'

export const SUPPLIER_RECOMMENDATION_ACTION_EXECUTABILITY_VERSION_V11428168 = 'V1.14.2.8.18.16.8'

const RULES = Object.freeze({
  CREATE_RECOMMENDATION_DECISION_CONTEXT: Object.freeze({ states: ['comparison_ready'], resultState: 'created' }),
  START_RECOMMENDATION_EVALUATION: Object.freeze({ states: ['created'], resultState: 'evaluating' }),
  PREPARE_RECOMMENDATION_DECISION: Object.freeze({ states: ['evaluating'], resultState: 'decision_prepared' }),
  START_MANUAL_REVIEW: Object.freeze({ states: ['decision_prepared'], resultState: 'manual_review' }),
  SELECT_RECOMMENDATION_SUPPLIER: Object.freeze({ states: ['manual_review'], resultState: 'manual_review' }),
  CONFIRM_RECOMMENDATION_DECISION: Object.freeze({ states: ['manual_review'], resultState: 'confirmed' }),
  PREPARE_PURCHASE_ORDER_GATE_HANDOFF: Object.freeze({ states: ['confirmed'], resultState: 'handoff_ready' }),
})

const text = value => String(value ?? '').trim()
const list = value => Array.isArray(value) ? value : []
const hasTaskIdentity = task => Boolean(text(task?.taskId) && text(task?.runtimeContextId))
const hasSingleRuntimeMaterial = runtimeContext => Boolean(text(runtimeContext?.runtimeContextNo)
  && text(runtimeContext?.materialCode) && text(runtimeContext?.quoteComparisonId))

function dataComplete(actionCode, facts = {}) {
  const { task, runtimeContext, context, approvalContext, candidate, input = {}, preparation } = facts
  if (!hasTaskIdentity(task) || !hasSingleRuntimeMaterial(runtimeContext)) return false
  if (actionCode === 'CREATE_RECOMMENDATION_DECISION_CONTEXT') {
    return Boolean(text(preparation?.recommendationPreparationNo)
      && list(preparation?.comparisons).length && list(preparation?.supplierCandidates).length)
  }
  if (!context || context.objectType !== 'SupplierRecommendationDecisionContext') return false
  if (actionCode === 'START_RECOMMENDATION_EVALUATION') return true
  if (actionCode === 'PREPARE_RECOMMENDATION_DECISION') {
    return list(context.evidence).length > 0 && list(context.supplierCandidates).length > 0
  }
  if (actionCode === 'START_MANUAL_REVIEW') return list(context.supplierCandidates).length > 0
  if (actionCode === 'SELECT_RECOMMENDATION_SUPPLIER') {
    return Boolean(text(candidate?.materialCode) && text(candidate?.supplierCode)
      && candidate.materialCode === runtimeContext.materialCode
      && list(context.supplierCandidates).some(item => item.materialCode === candidate.materialCode
        && item.supplierCode === candidate.supplierCode))
  }
  if (actionCode === 'CONFIRM_RECOMMENDATION_DECISION') {
    const selections = list(input.selections)
    return approvalContext?.objectType === 'RecommendationApprovalContext'
      && approvalContext.manualConfirmationStatus === 'pending'
      && Boolean(text(input.reason) && text(input.confirmedBy))
      && selections.length === 1 && selections[0].materialCode === runtimeContext.materialCode
      && list(context.supplierCandidates).some(item => item.materialCode === selections[0].materialCode
        && item.supplierCode === selections[0].supplierCode)
  }
  if (actionCode === 'PREPARE_PURCHASE_ORDER_GATE_HANDOFF') {
    const decision = facts.decision
    return decision?.objectType === 'SupplierRecommendationDecision'
      && decision.manualConfirmationStatus === 'confirmed'
      && Boolean(text(decision.confirmedBy) && decision.confirmedAt)
      && list(decision.selectedRecommendations).length === 1
  }
  return false
}

export function evaluateSupplierRecommendationActionExecutabilityV11428168({
  actionCode, state, facts = {}, permissionContext = {}, visible = true,
} = {}) {
  const rule = RULES[actionCode]
  const permissionAllowed = canPerformAction(permissionContext.role, 'EXECUTE')
  const stateGuard = actionCode === 'SELECT_RECOMMENDATION_SUPPLIER'
    || actionCode === 'CREATE_RECOMMENDATION_DECISION_CONTEXT'
    ? { allowed: Boolean(rule?.states.includes(state)), reason: 'STATE_NOT_ALLOWED' }
    : evaluateSupplierRecommendationActionGuardV1142811(actionCode, state)
  const stateAllowed = Boolean(rule && stateGuard.allowed)
  const complete = dataComplete(actionCode, facts)
  const executable = Boolean(visible && permissionAllowed && stateAllowed && complete)
  const reason = !visible ? 'ACTION_NOT_VISIBLE'
    : !permissionAllowed ? 'ACTION_PERMISSION_DENIED'
      : !stateAllowed ? 'ACTION_STATE_NOT_ALLOWED'
        : !complete ? 'ACTION_DATA_INCOMPLETE' : ''
  return Object.freeze({ actionCode, visible: Boolean(visible), executable,
    permissionAllowed, stateAllowed, dataComplete: complete,
    currentState: state, resultState: rule?.resultState || '', reason })
}

export function validateSupplierRecommendationActionResultV11428168(evaluation = {}, result = {}) {
  const actualState = result.context?.recommendationStatus || result.decision?.recommendationStatus
    || result.task?.status || ''
  const valid = evaluation.executable && result.result === 'PASS'
    && actualState === evaluation.resultState
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', expectedState: evaluation.resultState,
    actualState, reason: valid ? '' : 'ACTION_RESULT_STATE_MISMATCH' })
}

export const SUPPLIER_RECOMMENDATION_ACTION_EXECUTABILITY_RULES_V11428168 = RULES
