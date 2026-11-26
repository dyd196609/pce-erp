import { SUPPLIER_QUOTE_STATES } from './supplierQuoteStateContractV114289.js'
import { SUPPLIER_QUOTE_ACTION_CONTRACTS_V114289 } from './supplierQuoteActionContractsV114289.js'

export const SUPPLIER_QUOTE_NODE_CONTRACT_VERSION = 'V1.14.2.8.18.9'

export const SUPPLIER_QUOTE_NODE_CONTRACT_V114289 = Object.freeze({
  nodeCode: 'SCM_SUPPLIER_QUOTE',
  nodeName: '供应商报价',
  moduleCode: 'SCM',
  businessObject: 'SupplierQuote',
  sourceNode: 'SCM_PRICE_APPROVAL_PREPARATION',
  targetNode: 'SCM_QUOTE_COMPARISON_PREPARATION',
  inputObject: 'QuotePreparationContext',
  inputFields: Object.freeze(['quotePreparationNo', 'inquiryNo', 'sourceRequestNo', 'materialLines', 'supplierCandidates']),
  outputObject: 'QuoteComparisonPreparationContext',
  actions: Object.freeze(Object.keys(SUPPLIER_QUOTE_ACTION_CONTRACTS_V114289)),
  states: SUPPLIER_QUOTE_STATES,
  approvalContract: 'not_applicable',
  providerCode: 'SCM_SUPPLIER_QUOTE_PROVIDER',
  pageCode: 'supplier-quote-workbench',
  nextNode: 'SCM_QUOTE_COMPARISON_PREPARATION',
  forbiddenEffects: Object.freeze([
    'SEND_SUPPLIER', 'CALL_SUPPLIER_API', 'AUTO_CREATE_SUPPLIER_QUOTE',
    'CREATE_QUOTE_COMPARISON', 'CREATE_PURCHASE_ORDER', 'FINANCE_WRITE',
  ]),
})

export function validateSupplierQuoteNodeContract() {
  const contract = SUPPLIER_QUOTE_NODE_CONTRACT_V114289
  const valid = Boolean(contract.nodeCode && contract.inputObject && contract.outputObject
    && contract.actions.length === 3 && contract.states.length === 4
    && contract.providerCode && contract.pageCode && contract.nextNode
    && contract.approvalContract === 'not_applicable')
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL', contract })
}
