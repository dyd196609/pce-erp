import { createProcessStateTransitionContract } from '../../contract/processStateTransitionContract.js'

export const QUOTE_COMPARISON_STATE_TRANSITION_CONTRACT = createProcessStateTransitionContract({
  modelCode: 'QUOTE_COMPARISON_RUNTIME_STATE',
  objectType: 'QuoteComparison',
  initialState: 'supplier_quotes_ready',
  states: [
    'supplier_quotes_ready',
    'comparison_context_created',
    'comparing',
    'comparison_completed',
    'recommendation_ready',
  ],
  transitions: [
    { actionCode: 'CREATE_QUOTE_COMPARISON_CONTEXT', from: 'supplier_quotes_ready', to: 'comparison_context_created' },
    { actionCode: 'GENERATE_QUOTE_COMPARISON_FACT', from: 'comparison_context_created', to: 'comparing' },
    { actionCode: 'SAVE_QUOTE_COMPARISON', from: 'comparing', to: 'comparison_completed' },
    { actionCode: 'MARK_RECOMMENDATION_READY', from: 'comparison_completed', to: 'recommendation_ready' },
  ],
})

export const QUOTE_COMPARISON_STATE_BOUNDARIES = Object.freeze({
  comparison_context_created: Object.freeze({ objectType: 'QuoteComparisonContext', factOnly: true }),
  comparing: Object.freeze({ objectType: 'QuoteComparison', supplierRecommendationCreated: false }),
  comparison_completed: Object.freeze({ persistenceMode: 'session_runtime', supplierRecommendationCreated: false }),
  recommendation_ready: Object.freeze({ readinessOnly: true, supplierRecommendationCreated: false }),
})

export function validateQuoteComparisonStateBoundaries() {
  const values = Object.values(QUOTE_COMPARISON_STATE_BOUNDARIES)
  const valid = values.every(item => item.supplierRecommendationCreated !== true)
    && QUOTE_COMPARISON_STATE_BOUNDARIES.recommendation_ready.readinessOnly === true
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
