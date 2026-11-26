export const SUPPLIER_QUOTE_STATE_CONTRACT_VERSION = 'V1.14.2.8.18.9'

export const SUPPLIER_QUOTE_STATES = Object.freeze([
  'quote_preparation_ready',
  'supplier_quote_collecting',
  'supplier_quote_completed',
  'comparison_ready',
])

export const SUPPLIER_QUOTE_STATE_LABELS = Object.freeze({
  quote_preparation_ready: '报价准备已就绪',
  supplier_quote_collecting: '供应商报价收集中',
  supplier_quote_completed: '供应商报价收集完成',
  comparison_ready: '报价比较准备已就绪',
})

const transitions = Object.freeze({
  CREATE_SUPPLIER_QUOTE_CONTEXT: Object.freeze({ from: 'quote_preparation_ready', to: 'supplier_quote_collecting' }),
  SAVE_SUPPLIER_QUOTE: Object.freeze({ from: 'supplier_quote_collecting', to: 'supplier_quote_collecting' }),
  COMPLETE_SUPPLIER_QUOTE: Object.freeze({ from: 'supplier_quote_collecting', to: 'supplier_quote_completed' }),
  MARK_COMPARISON_READY: Object.freeze({ from: 'supplier_quote_completed', to: 'comparison_ready', internal: true }),
})

export function resolveSupplierQuoteStateTransition(currentState, actionCode) {
  const transition = transitions[actionCode]
  if (!transition || transition.from !== currentState) {
    return Object.freeze({ allowed: false, from: currentState, to: currentState,
      reason: 'SUPPLIER_QUOTE_STATE_TRANSITION_NOT_ALLOWED' })
  }
  return Object.freeze({ allowed: true, actionCode, ...transition })
}

export function resolveSupplierQuoteStatusLabel(statusCode = '') {
  return SUPPLIER_QUOTE_STATE_LABELS[statusCode] || '未知报价状态'
}

export const SUPPLIER_QUOTE_STATE_BOUNDARY = Object.freeze({
  comparisonReadyCreatesFormalComparison: false,
  supplierApiEnabled: false,
  supplierSendEnabled: false,
  purchaseOrderCreationEnabled: false,
  financeWriteEnabled: false,
})
