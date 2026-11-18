import { supplierCandidateProvider } from '../providers/supplierCandidateProvider.js'
import { createRecommendationApprovalContext, createSupplierRecommendationDecision,
  createSupplierRecommendationDecisionContext } from '../process/scm/supplierRecommendation/supplierRecommendationDomainModelV1142811.js'
import { evaluateSupplierRecommendationActionGuardV1142811 } from '../process/scm/supplierRecommendation/supplierRecommendationActionContractsV1142811.js'
import { resolveSupplierRecommendationTransitionV1142811 } from '../process/scm/supplierRecommendation/supplierRecommendationStateContractV1142811.js'
import { createSupplierRecommendationPurchaseOrderGateHandoffV1142816 } from '../process/scm/supplierRecommendation/supplierRecommendationPurchaseOrderGateHandoffV1142816.js'
import { supplierRecommendationRuntimeStoreV1142811 } from './supplierRecommendationRuntimeStoreV1142811.js'

export const SUPPLIER_RECOMMENDATION_ACTION_RUNTIME_VERSION_V1142811 = 'V1.14.2.8.18.11'
const boundaries = Object.freeze({ automaticRecommendation: false, aiDecision: false,
  purchaseOrderCreated: false, supplierContacted: false, financeCreated: false, wmsCreated: false, mesCreated: false })

const transitionContext = (context, actionCode, store, now = new Date().toISOString()) => {
  const guard = evaluateSupplierRecommendationActionGuardV1142811(actionCode, context.recommendationStatus)
  const transition = resolveSupplierRecommendationTransitionV1142811(context.recommendationStatus, actionCode)
  if (!guard.allowed || !transition.allowed) return Object.freeze({ result: 'FAIL', guard, transition, ...boundaries })
  const updated = store.saveContext({ ...context, recommendationStatus: transition.to,
    manualDecisionStatus: transition.to, updatedAt: now })
  return Object.freeze({ result: 'PASS', context: updated, transition, ...boundaries })
}

export function executeCreateRecommendationDecisionContext(preparation = {},
  store = supplierRecommendationRuntimeStoreV1142811, provider = supplierCandidateProvider) {
  const existing = store.findContextBySourceId(preparation.recommendationPreparationNo)
  if (existing) return Object.freeze({ result: 'PASS', idempotent: true, context: existing, ...boundaries })
  try {
    return Object.freeze({ result: 'PASS', idempotent: false,
      context: store.saveContext(createSupplierRecommendationDecisionContext(preparation, provider)), ...boundaries })
  } catch (error) { return Object.freeze({ result: 'FAIL', error: error.message, ...boundaries }) }
}

export const executeStartRecommendationEvaluation = (context, store = supplierRecommendationRuntimeStoreV1142811) =>
  transitionContext(context, 'START_RECOMMENDATION_EVALUATION', store)

export const executePrepareRecommendationDecision = (context, store = supplierRecommendationRuntimeStoreV1142811) => {
  if (!context.evidence?.length || !context.supplierCandidates?.length) {
    return Object.freeze({ result: 'FAIL', reason: 'RECOMMENDATION_EVIDENCE_INCOMPLETE', ...boundaries })
  }
  return transitionContext(context, 'PREPARE_RECOMMENDATION_DECISION', store)
}

export function executeStartManualReview(context, store = supplierRecommendationRuntimeStoreV1142811) {
  const transitioned = transitionContext(context, 'START_MANUAL_REVIEW', store)
  if (transitioned.result !== 'PASS') return transitioned
  try {
    const approvalContext = store.saveApprovalContext(createRecommendationApprovalContext(context))
    return Object.freeze({ ...transitioned, context: store.saveContext(transitioned.context), approvalContext })
  } catch (error) { return Object.freeze({ result: 'FAIL', error: error.message, ...boundaries }) }
}

export function executeConfirmRecommendationDecision(context, approvalContext, input = {},
  store = supplierRecommendationRuntimeStoreV1142811) {
  const guard = evaluateSupplierRecommendationActionGuardV1142811('CONFIRM_RECOMMENDATION_DECISION',
    context.recommendationStatus)
  const transition = resolveSupplierRecommendationTransitionV1142811(context.recommendationStatus,
    'CONFIRM_RECOMMENDATION_DECISION')
  if (!guard.allowed || !transition.allowed) return Object.freeze({ result: 'FAIL', guard, transition, ...boundaries })
  try {
    const decision = createSupplierRecommendationDecision(context, approvalContext, input)
    const savedDecision = store.saveDecision(decision)
    const updatedApproval = store.saveApprovalContext({ ...approvalContext,
      manualConfirmationStatus: 'confirmed', selectedRecommendations: decision.selectedRecommendations,
      recommendationReason: decision.recommendationReason, confirmedBy: decision.confirmedBy,
      confirmedAt: decision.confirmedAt, reviewStatus: 'confirmed', reviewer: decision.manualReviewer,
      reviewComment: decision.recommendationReason })
    const updatedContext = store.saveContext({ ...context, recommendationStatus: transition.to,
      manualDecisionStatus: transition.to,
      updatedAt: decision.confirmedAt })
    return Object.freeze({ result: 'PASS', context: updatedContext, approvalContext: updatedApproval,
      decision: savedDecision, transition, ...boundaries })
  } catch (error) { return Object.freeze({ result: 'FAIL', error: error.message, ...boundaries }) }
}

export function executePreparePurchaseOrderGateHandoff(decision = {},
  store = supplierRecommendationRuntimeStoreV1142811) {
  const guard = evaluateSupplierRecommendationActionGuardV1142811('PREPARE_PURCHASE_ORDER_GATE_HANDOFF',
    decision.recommendationStatus)
  const transition = resolveSupplierRecommendationTransitionV1142811(decision.recommendationStatus,
    'PREPARE_PURCHASE_ORDER_GATE_HANDOFF')
  if (!guard.allowed || !transition.allowed) return Object.freeze({ result: 'FAIL', guard, transition, ...boundaries })
  try {
    const readyDecision = store.saveDecision({ ...decision, recommendationStatus: transition.to,
      manualDecisionStatus: transition.to })
    const handoff = store.saveHandoff(createSupplierRecommendationPurchaseOrderGateHandoffV1142816(readyDecision))
    const context = store.listContexts().find(item => item.decisionContextNo === readyDecision.decisionContextNo)
    if (context) store.saveContext({ ...context, recommendationStatus: 'handoff_ready',
      manualDecisionStatus: 'handoff_ready', updatedAt: new Date().toISOString() })
    return Object.freeze({ result: 'PASS', decision: readyDecision, handoff, transition, ...boundaries })
  } catch (error) { return Object.freeze({ result: 'FAIL', error: error.message, ...boundaries }) }
}
