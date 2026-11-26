import { createProcessStateTransitionContract } from '../../contract/processStateTransitionContract.js'

export const SUPPLIER_RECOMMENDATION_STATE_TRANSITION_CONTRACT = createProcessStateTransitionContract({
  modelCode: 'SUPPLIER_RECOMMENDATION_RUNTIME_STATE',
  objectType: 'SupplierRecommendationDecision',
  initialState: 'quote_comparison_ready',
  states: [
    'quote_comparison_ready',
    'recommendation_context_created',
    'evaluating',
    'recommendation_completed',
    'approval_ready',
  ],
  transitions: [
    { actionCode: 'CREATE_RECOMMENDATION_CONTEXT', from: 'quote_comparison_ready', to: 'recommendation_context_created' },
    { actionCode: 'GENERATE_RECOMMENDATION_DECISION', from: 'recommendation_context_created', to: 'evaluating' },
    { actionCode: 'SAVE_RECOMMENDATION_DECISION', from: 'evaluating', to: 'recommendation_completed' },
    { actionCode: 'MARK_APPROVAL_READY', from: 'recommendation_completed', to: 'approval_ready' },
  ],
})

export const SUPPLIER_RECOMMENDATION_STATE_BOUNDARIES = Object.freeze({
  recommendation_context_created: Object.freeze({ objectType: 'SupplierRecommendationContext', factMapped: true }),
  evaluating: Object.freeze({ objectType: 'SupplierRecommendationDecision', approvalSubmitted: false }),
  recommendation_completed: Object.freeze({ persistenceMode: 'session_runtime', purchaseOrderCreated: false }),
  approval_ready: Object.freeze({ readinessOnly: true, approvalSubmitted: false, paymentCreated: false }),
})

export function validateSupplierRecommendationStateBoundaries() {
  const values = Object.values(SUPPLIER_RECOMMENDATION_STATE_BOUNDARIES)
  const valid = values.every(item => item.purchaseOrderCreated !== true
    && item.approvalSubmitted !== true && item.paymentCreated !== true)
    && SUPPLIER_RECOMMENDATION_STATE_BOUNDARIES.approval_ready.readinessOnly === true
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
