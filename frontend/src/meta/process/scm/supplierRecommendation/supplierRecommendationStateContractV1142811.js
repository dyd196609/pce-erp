import { createProcessStateTransitionContract, resolveStateTransition } from '../../contract/processStateTransitionContract.js'

export const SUPPLIER_RECOMMENDATION_STATE_VERSION_V1142811 = 'V1.14.2.8.18.11'
export const SUPPLIER_RECOMMENDATION_STATES_V1142811 = Object.freeze([
  'created', 'evaluating', 'decision_prepared', 'manual_review', 'confirmed', 'handoff_ready',
])

export const SUPPLIER_RECOMMENDATION_STATE_CONTRACT_V1142811 = createProcessStateTransitionContract({
  modelCode: 'SUPPLIER_RECOMMENDATION_DECISION_STATE_V1142811',
  objectType: 'SupplierRecommendationDecisionContext',
  initialState: 'created',
  states: SUPPLIER_RECOMMENDATION_STATES_V1142811,
  transitions: [
    { actionCode: 'START_RECOMMENDATION_EVALUATION', from: 'created', to: 'evaluating' },
    { actionCode: 'PREPARE_RECOMMENDATION_DECISION', from: 'evaluating', to: 'decision_prepared' },
    { actionCode: 'START_MANUAL_REVIEW', from: 'decision_prepared', to: 'manual_review' },
    { actionCode: 'CONFIRM_RECOMMENDATION_DECISION', from: 'manual_review', to: 'confirmed' },
    { actionCode: 'PREPARE_PURCHASE_ORDER_GATE_HANDOFF', from: 'confirmed', to: 'handoff_ready' },
  ],
})

export const SUPPLIER_RECOMMENDATION_STATUS_LABELS_V1142811 = Object.freeze({
  comparison_ready: '报价比较已就绪', created: '决策上下文已创建', evaluating: '正在整理推荐依据',
  decision_prepared: '推荐决策已准备', manual_review: '待人工确认', confirmed: '推荐结果已确认',
  handoff_ready: '采购订单准入交接已就绪',
})

export const SUPPLIER_RECOMMENDATION_BOUNDARY_V1142811 = Object.freeze({
  automaticRecommendation: false, aiDecision: false, purchaseOrderCreated: false,
  supplierContacted: false, financeCreated: false, wmsCreated: false, mesCreated: false,
})

export function resolveSupplierRecommendationTransitionV1142811(state, actionCode) {
  try { return Object.freeze({ allowed: true,
    ...resolveStateTransition(SUPPLIER_RECOMMENDATION_STATE_CONTRACT_V1142811, state, actionCode) }) }
  catch (error) { return Object.freeze({ allowed: false, from: state, actionCode, reason: error.message }) }
}

export const resolveSupplierRecommendationStatusLabelV1142811 = state =>
  SUPPLIER_RECOMMENDATION_STATUS_LABELS_V1142811[state] || '状态待确认'
