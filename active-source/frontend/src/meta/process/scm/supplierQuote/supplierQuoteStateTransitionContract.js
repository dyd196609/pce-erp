import { createProcessStateTransitionContract } from '../../contract/processStateTransitionContract.js'

export const SUPPLIER_QUOTE_STATE_TRANSITION_CONTRACT = createProcessStateTransitionContract({
  modelCode: 'SUPPLIER_QUOTE_RUNTIME_STATE',
  objectType: 'SupplierQuote',
  initialState: 'purchase_inquiry_ready',
  states: [
    'purchase_inquiry_ready',
    'quote_context_created',
    'waiting_supplier_quote',
    'quotation_received',
    'quotation_completed',
    'comparison_ready',
  ],
  transitions: [
    { actionCode: 'CREATE_SUPPLIER_QUOTE_CONTEXT', from: 'purchase_inquiry_ready', to: 'quote_context_created' },
    { actionCode: 'WAIT_FOR_SUPPLIER_QUOTE', from: 'quote_context_created', to: 'waiting_supplier_quote' },
    { actionCode: 'RECEIVE_SUPPLIER_QUOTE', from: 'waiting_supplier_quote', to: 'quotation_received' },
    { actionCode: 'SAVE_SUPPLIER_QUOTE', from: 'quotation_received', to: 'quotation_completed' },
    { actionCode: 'MARK_COMPARISON_READY', from: 'quotation_completed', to: 'comparison_ready' },
  ],
})

export const SUPPLIER_QUOTE_STATE_BOUNDARIES = Object.freeze({
  quote_context_created: Object.freeze({ objectType: 'SupplierQuoteContext', supplierApiCalled: false }),
  waiting_supplier_quote: Object.freeze({ receiveMode: 'manual_only', supplierApiCalled: false }),
  quotation_received: Object.freeze({ objectType: 'SupplierQuote', quoteComparisonCreated: false }),
  quotation_completed: Object.freeze({ persistenceMode: 'session_runtime', quoteComparisonCreated: false }),
  comparison_ready: Object.freeze({ readinessOnly: true, quoteComparisonCreated: false }),
})

export function validateSupplierQuoteStateBoundaries() {
  const values = Object.values(SUPPLIER_QUOTE_STATE_BOUNDARIES)
  const valid = values.every(item => item.supplierApiCalled !== true && item.quoteComparisonCreated !== true)
    && SUPPLIER_QUOTE_STATE_BOUNDARIES.comparison_ready.readinessOnly === true
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

