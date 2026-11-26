import { createProcessHandoffContract } from '../../contract/processHandoffContract.js'
import { createQuoteComparisonPreparationContext } from './quoteComparisonDomainModelV1142810.js'

export const SUPPLIER_QUOTE_TO_QUOTE_COMPARISON_HANDOFF = createProcessHandoffContract({
  handoffCode: 'SUPPLIER_QUOTE_TO_QUOTE_COMPARISON',
  fromNode: 'SCM_SUPPLIER_QUOTE',
  toNode: 'SCM_QUOTE_COMPARISON',
  outputObject: 'SupplierQuoteContext',
  inputObject: 'QuoteComparisonPreparationContext',
  mappingCode: 'MAP_SUPPLIER_QUOTES_TO_QUOTE_COMPARISON_V1142810',
  actionCode: 'CREATE_QUOTE_COMPARISON_CONTEXT',
  requiredContextKeys: ['inquiryNo', 'sourceRequestNo', 'materialLines', 'supplierQuotes'],
})

export function createSupplierQuoteToQuoteComparisonHandoff(sourceFacts = {}) {
  const context = createQuoteComparisonPreparationContext(sourceFacts)
  const valid = context.sourceInquiryNo === sourceFacts.inquiryNo
    && context.sourceRequestNo === sourceFacts.sourceRequestNo
    && context.materialLines.length === sourceFacts.materialLines.length
    && context.supplierQuotes.length === sourceFacts.supplierQuotes.length
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid,
    source: 'SupplierQuoteContext', target: 'QuoteComparisonPreparationContext',
    transferredFields: Object.freeze(['inquiryNo', 'sourceRequestNo', 'materialLines', 'supplierQuotes']), context })
}
