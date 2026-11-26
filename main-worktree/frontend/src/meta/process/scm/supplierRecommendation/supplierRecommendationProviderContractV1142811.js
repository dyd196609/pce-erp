export const SUPPLIER_RECOMMENDATION_PROVIDER_CONTRACT_V1142811 = Object.freeze({
  version: 'V1.14.2.8.18.11', providerCode: 'SCM_SUPPLIER_RECOMMENDATION_PROVIDER',
  factOwner: 'SupplierRecommendationRuntimeStore', upstreamFactSource: 'QuoteComparisonRuntimeStore',
  outputs: Object.freeze(['records', 'contexts', 'approvalContexts', 'decisions', 'handoffs', 'current']),
  lifecycle: Object.freeze(['first_load', 'refresh', 'reopen']),
  legacyMockAllowed: false, urlStateAllowed: false, automaticRecommendationAllowed: false,
})

export function validateSupplierRecommendationProviderContractV1142811() {
  const value = SUPPLIER_RECOMMENDATION_PROVIDER_CONTRACT_V1142811
  const valid = value.providerCode === 'SCM_SUPPLIER_RECOMMENDATION_PROVIDER'
    && value.factOwner === 'SupplierRecommendationRuntimeStore'
    && value.upstreamFactSource === 'QuoteComparisonRuntimeStore'
    && value.lifecycle.length === 3 && !value.legacyMockAllowed && !value.urlStateAllowed
    && !value.automaticRecommendationAllowed
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL', contract: value })
}
