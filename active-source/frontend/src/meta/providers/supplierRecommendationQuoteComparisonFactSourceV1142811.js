import { getProfitSession } from '../demo/demoMode.js'
import { quoteComparisonRuntimeStoreV1142810 } from '../runtime/quoteComparisonRuntimeStoreV1142810.js'
import { SUPPLIER_RECOMMENDATION_READ_ONLY_QUOTE_COMPARISON_FACTS_V1142811 } from '../acceptance/supplierRecommendationQuoteComparisonTestFactsV1142811.js'

export const SUPPLIER_RECOMMENDATION_QUOTE_FACT_SOURCE_VERSION_V1142811 = 'V1.14.2.8.18.11'

export function createSupplierRecommendationQuoteComparisonFactSourceV1142811({
  runtimeStore = quoteComparisonRuntimeStoreV1142810,
  acceptanceFacts = SUPPLIER_RECOMMENDATION_READ_ONLY_QUOTE_COMPARISON_FACTS_V1142811,
  acceptanceModeResolver = () => getProfitSession().demoMode === true,
} = {}) {
  return Object.freeze({
    sourceCode: 'SCM_QUOTE_COMPARISON_RECOMMENDATION_FACT_SOURCE',
    readOnlyAcceptanceSource: true,
    productionWriteAllowed: false,
    listRecommendationPreparations() {
      const runtimeFacts = runtimeStore.listRecommendationPreparations()
      if (!acceptanceModeResolver()) return Object.freeze([...runtimeFacts])
      const existing = new Set(runtimeFacts.map(item => item.recommendationPreparationNo))
      return Object.freeze([...runtimeFacts,
        ...acceptanceFacts.filter(item => !existing.has(item.recommendationPreparationNo))])
    },
  })
}

export const supplierRecommendationQuoteComparisonFactSourceV1142811 =
  createSupplierRecommendationQuoteComparisonFactSourceV1142811()
