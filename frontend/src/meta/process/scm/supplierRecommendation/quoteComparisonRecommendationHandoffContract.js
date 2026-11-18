import { createProcessHandoffContract } from '../../contract/processHandoffContract.js'
import {
  QUOTE_COMPARISON_HANDOFF_SOURCE_NODE_CODE,
  SUPPLIER_RECOMMENDATION_NODE_CODE,
} from './supplierRecommendationNodeRuntimeContract.js'

export const QUOTE_COMPARISON_RECOMMENDATION_HANDOFF_CONTRACT = createProcessHandoffContract({
  handoffCode: 'QUOTE_COMPARISON_TO_SUPPLIER_RECOMMENDATION_CONTEXT',
  fromNode: QUOTE_COMPARISON_HANDOFF_SOURCE_NODE_CODE,
  toNode: SUPPLIER_RECOMMENDATION_NODE_CODE,
  outputObject: 'QuoteComparison',
  inputObject: 'SupplierRecommendationContext',
  mappingCode: 'MAP_QUOTE_COMPARISON_TO_SUPPLIER_RECOMMENDATION_CONTEXT',
  actionCode: 'CREATE_RECOMMENDATION_CONTEXT',
  requiredContextKeys: ['processInstanceId', 'objectId', 'correlationId', 'state'],
})

export function validateQuoteComparisonRecommendationHandoff(comparison = {}, context = {}) {
  const suppliers = new Set((comparison.facts || []).map(item => item.supplierId))
  const valid = comparison.objectType === 'QuoteComparison'
    && ['comparison_completed', 'recommendation_ready'].includes(comparison.status)
    && context.objectType === 'SupplierRecommendationContext'
    && context.comparisonNo === comparison.comparisonNo
    && context.comparisonResult?.comparisonNo === comparison.comparisonNo
    && context.suppliers.length === suppliers.size
    && context.suppliers.every(item => suppliers.has(item.supplierId))
    && context.priceEvidence.length === comparison.facts.length
    && context.deliveryEvidence.length === comparison.facts.length
    && context.riskEvidence.length > 0
  return Object.freeze({
    result: valid ? 'PASS' : 'FAIL',
    valid,
    transferredFields: Object.freeze([
      'comparisonResult',
      'suppliers',
      'priceEvidence',
      'deliveryEvidence',
      'riskEvidence',
    ]),
    mappingCode: QUOTE_COMPARISON_RECOMMENDATION_HANDOFF_CONTRACT.mappingCode,
  })
}
