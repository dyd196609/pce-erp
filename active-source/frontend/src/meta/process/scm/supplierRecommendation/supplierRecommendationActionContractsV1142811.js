import { createProcessActionRuntimeContract } from '../../contract/processActionRuntimeContract.js'
import { SUPPLIER_RECOMMENDATION_NODE_CODE_V1142811 } from './supplierRecommendationNodeContractV1142811.js'

const base = { nodeCode: SUPPLIER_RECOMMENDATION_NODE_CODE_V1142811,
  objectType: 'SupplierRecommendationDecisionContext', stateModel: 'SUPPLIER_RECOMMENDATION_DECISION_STATE_V1142811' }

const action = (actionCode, actionName, allowedFromStates, resultState, handoffCode = null) =>
  createProcessActionRuntimeContract({ ...base, actionCode, actionName,
    buttonCode: actionCode.toLowerCase().replaceAll('_', '-'), allowedFromStates, resultState, handoffCode })

export const SUPPLIER_RECOMMENDATION_ACTION_CONTRACTS_V1142811 = Object.freeze([
  action('CREATE_RECOMMENDATION_DECISION_CONTEXT', '建立推荐决策上下文', ['comparison_ready'], 'created',
    'QUOTE_COMPARISON_TO_RECOMMENDATION_DECISION_PREPARATION'),
  action('START_RECOMMENDATION_EVALUATION', '整理推荐依据', ['created'], 'evaluating'),
  action('PREPARE_RECOMMENDATION_DECISION', '准备人工推荐决策', ['evaluating'], 'decision_prepared'),
  action('START_MANUAL_REVIEW', '开始人工确认', ['decision_prepared'], 'manual_review'),
  action('CONFIRM_RECOMMENDATION_DECISION', '确认推荐结果', ['manual_review'], 'confirmed'),
  action('PREPARE_PURCHASE_ORDER_GATE_HANDOFF', '准备采购订单准入交接', ['confirmed'], 'handoff_ready',
    'SUPPLIER_RECOMMENDATION_TO_PURCHASE_ORDER_GATE'),
])

export const SUPPLIER_RECOMMENDATION_FORBIDDEN_ACTIONS_V1142811 = Object.freeze([
  'AUTO_RECOMMEND_SUPPLIER', 'AI_DECIDE_SUPPLIER', 'CREATE_PURCHASE_ORDER', 'SEND_SUPPLIER',
  'FINANCE_WRITE', 'WMS_WRITE', 'MES_WRITE',
])

export const SUPPLIER_RECOMMENDATION_ALLOWED_BUSINESS_ACTIONS_V1142811 = Object.freeze([
  'prepareRecommendationDecision', 'submitManualReview', 'confirmRecommendation',
])

export const SUPPLIER_RECOMMENDATION_FORBIDDEN_BUSINESS_ACTIONS_V1142811 = Object.freeze([
  'autoRecommendSupplier', 'createPurchaseOrder', 'sendSupplier', 'executePurchaseOrder',
  'financeWrite', 'warehouseWrite', 'mesWrite',
])

export function evaluateSupplierRecommendationActionGuardV1142811(actionCode, state) {
  if (SUPPLIER_RECOMMENDATION_FORBIDDEN_ACTIONS_V1142811.includes(actionCode)) {
    return Object.freeze({ allowed: false, reason: 'ACTION_OUTSIDE_SUPPLIER_RECOMMENDATION_BOUNDARY' })
  }
  const contract = SUPPLIER_RECOMMENDATION_ACTION_CONTRACTS_V1142811.find(item => item.actionCode === actionCode)
  return Object.freeze(contract?.allowedFromStates.includes(state)
    ? { allowed: true, reason: '' }
    : { allowed: false, reason: contract ? 'STATE_NOT_ALLOWED' : 'ACTION_NOT_REGISTERED' })
}
