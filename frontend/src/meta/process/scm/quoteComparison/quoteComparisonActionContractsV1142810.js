import { createProcessActionRuntimeContract } from '../../contract/processActionRuntimeContract.js'

export const QUOTE_COMPARISON_ACTION_VERSION = 'V1.14.2.8.18.10'
const base = { nodeCode: 'SCM_QUOTE_COMPARISON', objectType: 'QuoteComparisonPreparationContext',
  stateModel: 'QUOTE_COMPARISON_STATE_V1142810' }

export const QUOTE_COMPARISON_ACTION_CONTRACTS_V1142810 = Object.freeze({
  CREATE_QUOTE_COMPARISON_CONTEXT: createProcessActionRuntimeContract({ ...base,
    actionCode: 'CREATE_QUOTE_COMPARISON_CONTEXT', actionName: '创建报价比较上下文',
    buttonCode: 'create-quote-comparison-context', allowedFromStates: ['comparison_ready'],
    resultState: 'supplier_quote_completed', handoffCode: 'SUPPLIER_QUOTE_TO_QUOTE_COMPARISON' }),
  GENERATE_QUOTE_COMPARISON: createProcessActionRuntimeContract({ ...base,
    actionCode: 'GENERATE_QUOTE_COMPARISON', actionName: '生成报价比较',
    buttonCode: 'generate-quote-comparison', allowedFromStates: ['supplier_quote_completed'],
    resultState: 'comparison_preparing' }),
  SAVE_QUOTE_COMPARISON: createProcessActionRuntimeContract({ ...base,
    actionCode: 'SAVE_QUOTE_COMPARISON', actionName: '保存报价比较',
    buttonCode: 'save-quote-comparison', allowedFromStates: ['comparison_preparing'],
    resultState: 'comparison_ready' }),
})

export const QUOTE_COMPARISON_FORBIDDEN_ACTIONS = Object.freeze([
  'CREATE_SUPPLIER_RECOMMENDATION', 'CREATE_PURCHASE_ORDER', 'FINANCE_WRITE',
])

export function evaluateQuoteComparisonActionGuard(actionCode, state) {
  if (QUOTE_COMPARISON_FORBIDDEN_ACTIONS.includes(actionCode)) {
    return Object.freeze({ allowed: false, reason: 'ACTION_OUTSIDE_QUOTE_COMPARISON_BOUNDARY' })
  }
  const contract = QUOTE_COMPARISON_ACTION_CONTRACTS_V1142810[actionCode]
  return Object.freeze({ allowed: Boolean(contract?.allowedFromStates.includes(state)),
    reason: contract?.allowedFromStates.includes(state) ? '' : 'ACTION_STATE_NOT_ALLOWED' })
}
