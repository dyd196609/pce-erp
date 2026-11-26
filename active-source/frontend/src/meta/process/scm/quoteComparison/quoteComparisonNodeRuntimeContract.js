import { createProcessNodeRuntimeContract } from '../../contract/processNodeRuntimeContract.js'

export const QUOTE_COMPARISON_NODE_CODE = 'SCM_QUOTE_COMPARISON'
export const SUPPLIER_QUOTE_HANDOFF_SOURCE_NODE_CODE = 'SCM_SUPPLIER_QUOTE_HANDOFF'

export const QUOTE_COMPARISON_NODE_RUNTIME_CONTRACT = createProcessNodeRuntimeContract({
  nodeCode: QUOTE_COMPARISON_NODE_CODE,
  nodeName: 'SCM Quote Comparison',
  inputObject: 'QuoteComparisonContext',
  outputObject: 'QuoteComparison',
  actions: [
    'CREATE_QUOTE_COMPARISON_CONTEXT',
    'GENERATE_QUOTE_COMPARISON_FACT',
    'SAVE_QUOTE_COMPARISON',
  ],
  stateModel: 'QUOTE_COMPARISON_RUNTIME_STATE',
  nextNode: null,
})

export const SUPPLIER_QUOTE_HANDOFF_SOURCE = Object.freeze({
  nodeCode: SUPPLIER_QUOTE_HANDOFF_SOURCE_NODE_CODE,
  nodeName: 'Supplier Quote Handoff',
  inputObject: 'SupplierQuoteContext',
  outputObject: 'SupplierQuote[]',
  nextNode: QUOTE_COMPARISON_NODE_CODE,
  handoffActionOwner: 'target',
})
