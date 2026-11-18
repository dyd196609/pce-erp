import { createSupplierQuoteContextModel } from './supplierQuoteDomainModelV114289.js'

export const QUOTE_PREPARATION_TO_SUPPLIER_QUOTE_HANDOFF_VERSION = 'V1.14.2.8.18.9'

export const QUOTE_PREPARATION_TO_SUPPLIER_QUOTE_HANDOFF_CONTRACT = Object.freeze({
  handoffCode: 'QUOTE_PREPARATION_TO_SUPPLIER_QUOTE',
  source: 'QuotePreparationContext',
  target: 'SupplierQuoteContext',
  actionCode: 'CREATE_SUPPLIER_QUOTE_CONTEXT',
  requiredFields: Object.freeze(['inquiryNo', 'sourceRequestNo', 'materialLines', 'supplierCandidates']),
  targetProvider: 'SCM_SUPPLIER_QUOTE_PROVIDER',
  createsSupplierQuoteAutomatically: false,
  callsSupplierApi: false,
})

export function createQuotePreparationToSupplierQuoteHandoff(preparation = {}) {
  const missingFields = QUOTE_PREPARATION_TO_SUPPLIER_QUOTE_HANDOFF_CONTRACT.requiredFields
    .filter(field => Array.isArray(preparation[field]) ? preparation[field].length === 0 : !preparation[field])
  if (missingFields.length) return Object.freeze({ result: 'FAIL', valid: false, missingFields: Object.freeze(missingFields) })
  try {
    const context = createSupplierQuoteContextModel(preparation)
    return Object.freeze({ result: 'PASS', valid: true, context,
      transferredFields: QUOTE_PREPARATION_TO_SUPPLIER_QUOTE_HANDOFF_CONTRACT.requiredFields,
      supplierQuoteCreated: false, supplierApiCalled: false })
  } catch (error) {
    return Object.freeze({ result: 'FAIL', valid: false, error: error.message, missingFields: Object.freeze([]) })
  }
}
