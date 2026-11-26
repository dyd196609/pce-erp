export const SUPPLIER_RECOMMENDATION_PAGE_CONTRACT_V1142811 = Object.freeze({
  version: 'V1.14.2.8.18.17', pageCode: 'supplier-recommendation', pageName: '供应商推荐',
  route: '/scm/supplier-recommendation', moduleCode: 'SCM', businessObject: 'SupplierRecommendationDecisionBatch',
  providerCode: 'SCM_SUPPLIER_RECOMMENDATION_PROVIDER', previousModule: 'quote-comparison',
  currentModule: 'supplier-recommendation', nextModule: 'purchase-order-gate',
  regions: Object.freeze(['purchase-context', 'material-recommendation-list', 'supplier-comparison',
    'historical-price-reference', 'manual-recommendation-decision', 'batch-confirmation']),
})

export function validateSupplierRecommendationPageContractV1142811() {
  const value = SUPPLIER_RECOMMENDATION_PAGE_CONTRACT_V1142811
  const valid = ['pageCode', 'pageName', 'route', 'moduleCode', 'businessObject', 'providerCode']
    .every(key => Boolean(value[key])) && value.regions.length === 6
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL', contract: value })
}
