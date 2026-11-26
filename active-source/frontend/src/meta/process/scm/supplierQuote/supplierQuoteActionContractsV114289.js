export const SUPPLIER_QUOTE_ACTION_CONTRACT_VERSION = 'V1.14.2.8.18.9'

export const SUPPLIER_QUOTE_ACTION_CONTRACTS_V114289 = Object.freeze({
  CREATE_SUPPLIER_QUOTE_CONTEXT: Object.freeze({
    actionCode: 'CREATE_SUPPLIER_QUOTE_CONTEXT', actionName: '进入供应商报价',
    allowedStates: Object.freeze(['quote_preparation_ready']), inputObject: 'QuotePreparationContext',
    outputObject: 'SupplierQuoteContext', resultState: 'supplier_quote_collecting',
    idempotencyKey: 'quotePreparationNo', permission: 'supplier_quote.context.create',
  }),
  SAVE_SUPPLIER_QUOTE: Object.freeze({
    actionCode: 'SAVE_SUPPLIER_QUOTE', actionName: '保存报价',
    allowedStates: Object.freeze(['supplier_quote_collecting']), inputObject: 'SupplierQuote',
    outputObject: 'SupplierQuote', resultState: 'supplier_quote_collecting',
    idempotencyKey: 'supplierQuoteContextNo:materialCode:supplierCode', permission: 'supplier_quote.save',
  }),
  COMPLETE_SUPPLIER_QUOTE: Object.freeze({
    actionCode: 'COMPLETE_SUPPLIER_QUOTE', actionName: '完成报价收集',
    allowedStates: Object.freeze(['supplier_quote_collecting']), inputObject: 'SupplierQuoteContext',
    outputObject: 'QuoteComparisonPreparationContext', resultState: 'comparison_ready',
    idempotencyKey: 'supplierQuoteContextNo:comparison_ready', permission: 'supplier_quote.complete',
  }),
})

export const SUPPLIER_QUOTE_FORBIDDEN_ACTIONS = Object.freeze([
  'SEND_SUPPLIER',
  'CALL_SUPPLIER_API',
  'CREATE_PURCHASE_ORDER',
  'CREATE_QUOTE_COMPARISON',
])

export function resolveSupplierQuoteActionContract(actionCode = '') {
  return SUPPLIER_QUOTE_ACTION_CONTRACTS_V114289[actionCode] || null
}

export function evaluateSupplierQuoteActionGuard(actionCode, currentState) {
  if (SUPPLIER_QUOTE_FORBIDDEN_ACTIONS.includes(actionCode)) {
    return Object.freeze({ allowed: false, actionCode, reason: 'SUPPLIER_QUOTE_FORBIDDEN_ACTION' })
  }
  const contract = resolveSupplierQuoteActionContract(actionCode)
  const allowed = Boolean(contract?.allowedStates.includes(currentState))
  return Object.freeze({ allowed, actionCode,
    reason: allowed ? 'ACTION_ALLOWED' : contract ? 'SUPPLIER_QUOTE_ACTION_STATE_NOT_ALLOWED' : 'ACTION_NOT_REGISTERED',
    contract })
}
