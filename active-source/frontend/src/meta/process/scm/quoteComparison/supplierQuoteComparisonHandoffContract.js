import { createProcessHandoffContract } from '../../contract/processHandoffContract.js'
import {
  QUOTE_COMPARISON_NODE_CODE,
  SUPPLIER_QUOTE_HANDOFF_SOURCE_NODE_CODE,
} from './quoteComparisonNodeRuntimeContract.js'

export const SUPPLIER_QUOTE_COMPARISON_HANDOFF_CONTRACT = createProcessHandoffContract({
  handoffCode: 'SUPPLIER_QUOTES_TO_QUOTE_COMPARISON_CONTEXT',
  fromNode: SUPPLIER_QUOTE_HANDOFF_SOURCE_NODE_CODE,
  toNode: QUOTE_COMPARISON_NODE_CODE,
  outputObject: 'SupplierQuote[]',
  inputObject: 'QuoteComparisonContext',
  mappingCode: 'MAP_SUPPLIER_QUOTES_TO_QUOTE_COMPARISON_CONTEXT',
  actionCode: 'CREATE_QUOTE_COMPARISON_CONTEXT',
  requiredContextKeys: ['processInstanceId', 'objectId', 'correlationId', 'state'],
})

export function validateSupplierQuoteComparisonHandoff(quotes = [], context = {}) {
  const sourceQuoteNos = quotes.map(item => item.quoteNo).sort()
  const targetQuoteNos = (context.quotes || []).map(item => item.quoteNo).sort()
  const valid = quotes.length > 0
    && context.objectType === 'QuoteComparisonContext'
    && context.status === 'comparison_context_created'
    && sourceQuoteNos.length === targetQuoteNos.length
    && sourceQuoteNos.every((quoteNo, index) => quoteNo && quoteNo === targetQuoteNos[index])
    && context.quotes.every(item => item.supplierId && item.materials.length > 0
      && item.materials.every(line => line.materialCode && line.quantity > 0 && line.unitPrice > 0
        && line.deliveryDate && line.validUntil))
  return Object.freeze({
    result: valid ? 'PASS' : 'FAIL',
    valid,
    transferredFields: Object.freeze([
      'supplier',
      'quote',
      'materials',
      'quantity',
      'price',
      'deliveryDate',
      'validUntil',
    ]),
    mappingCode: SUPPLIER_QUOTE_COMPARISON_HANDOFF_CONTRACT.mappingCode,
  })
}
