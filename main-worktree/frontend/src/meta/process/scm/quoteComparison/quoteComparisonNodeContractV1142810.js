import { QUOTE_COMPARISON_STATES_V1142810 } from './quoteComparisonStateContractV1142810.js'
import { QUOTE_COMPARISON_ACTION_CONTRACTS_V1142810 } from './quoteComparisonActionContractsV1142810.js'

export const QUOTE_COMPARISON_NODE_CONTRACT_V1142810 = Object.freeze({
  version: 'V1.14.2.8.18.10', nodeCode: 'SCM_QUOTE_COMPARISON', nodeName: '报价比较', moduleCode: 'SCM',
  businessObject: 'QuoteComparison', sourceNode: 'SCM_SUPPLIER_QUOTE',
  targetNode: 'SCM_SUPPLIER_RECOMMENDATION_DECISION_PREPARATION',
  inputObject: 'SupplierQuoteContext', outputObject: 'SupplierRecommendationDecisionPreparationContext',
  actions: Object.freeze(Object.keys(QUOTE_COMPARISON_ACTION_CONTRACTS_V1142810)),
  states: QUOTE_COMPARISON_STATES_V1142810, approvalContract: 'not_applicable',
  providerCode: 'SCM_QUOTE_COMPARISON_PROVIDER', pageCode: 'quote-comparison-workbench',
  forbiddenEffects: Object.freeze(['CREATE_SUPPLIER_RECOMMENDATION', 'CREATE_PURCHASE_ORDER', 'FINANCE_WRITE']),
})

export function validateQuoteComparisonNodeContractV1142810() {
  const value = QUOTE_COMPARISON_NODE_CONTRACT_V1142810
  const valid = value.actions.length === 3 && value.states.length === 3 && value.approvalContract === 'not_applicable'
    && value.inputObject === 'SupplierQuoteContext' && value.outputObject === 'SupplierRecommendationDecisionPreparationContext'
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL', contract: value })
}
