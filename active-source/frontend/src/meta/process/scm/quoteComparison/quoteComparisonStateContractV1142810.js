import { createProcessStateTransitionContract, resolveStateTransition } from '../../contract/processStateTransitionContract.js'

export const QUOTE_COMPARISON_STATE_VERSION = 'V1.14.2.8.18.10'
export const QUOTE_COMPARISON_STATES_V1142810 = Object.freeze([
  'supplier_quote_completed', 'comparison_preparing', 'comparison_ready',
])

export const QUOTE_COMPARISON_STATE_CONTRACT_V1142810 = createProcessStateTransitionContract({
  modelCode: 'QUOTE_COMPARISON_STATE_V1142810',
  objectType: 'QuoteComparisonPreparationContext',
  initialState: 'supplier_quote_completed',
  states: QUOTE_COMPARISON_STATES_V1142810,
  transitions: [
    { actionCode: 'GENERATE_QUOTE_COMPARISON', from: 'supplier_quote_completed', to: 'comparison_preparing' },
    { actionCode: 'SAVE_QUOTE_COMPARISON', from: 'comparison_preparing', to: 'comparison_ready' },
  ],
})

export const QUOTE_COMPARISON_STATUS_LABELS = Object.freeze({
  supplier_quote_completed: '供应商报价已完成',
  comparison_preparing: '正在生成比较结果',
  comparison_ready: '比较准备完成',
})

export const QUOTE_COMPARISON_BOUNDARY = Object.freeze({
  comparisonReadyCreatesRecommendation: false,
  comparisonReadyCreatesPurchaseOrder: false,
  comparisonReadyCreatesFinanceObject: false,
})

export function resolveQuoteComparisonTransition(state, actionCode) {
  try { return Object.freeze({ allowed: true, ...resolveStateTransition(QUOTE_COMPARISON_STATE_CONTRACT_V1142810, state, actionCode) }) }
  catch (error) { return Object.freeze({ allowed: false, from: state, actionCode, reason: error.message }) }
}

export const resolveQuoteComparisonStatusLabel = state => QUOTE_COMPARISON_STATUS_LABELS[state] || '状态待确认'
