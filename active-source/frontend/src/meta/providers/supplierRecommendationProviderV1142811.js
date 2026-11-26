import { supplierRecommendationQuoteComparisonFactSourceV1142811 } from './supplierRecommendationQuoteComparisonFactSourceV1142811.js'
import { supplierRecommendationRuntimeStoreV1142811 } from '../runtime/supplierRecommendationRuntimeStoreV1142811.js'
import { resolveSupplierRecommendationStatusLabelV1142811 } from '../process/scm/supplierRecommendation/supplierRecommendationStateContractV1142811.js'

export const SUPPLIER_RECOMMENDATION_PROVIDER_VERSION_V1142811 = 'V1.14.2.8.18.11'

export function createSupplierRecommendationProviderV1142811({ sourceStore = supplierRecommendationQuoteComparisonFactSourceV1142811,
  store = supplierRecommendationRuntimeStoreV1142811 } = {}) {
  return Object.freeze({
    providerCode: 'SCM_SUPPLIER_RECOMMENDATION_PROVIDER',
    factSource: 'SupplierRecommendationRuntimeStore', upstreamFactSource: 'QuoteComparisonRuntimeStore',
    load({ sourceInquiryNo = '' } = {}) {
      const preparations = sourceStore.listRecommendationPreparations().filter(item =>
        !sourceInquiryNo || item.sourceInquiryNo === sourceInquiryNo)
      const contexts = store.listContexts().filter(item => !sourceInquiryNo || item.sourceInquiryNo === sourceInquiryNo)
      const approvalContexts = store.listApprovalContexts()
      const decisions = store.listDecisions().filter(item => !sourceInquiryNo || item.sourceInquiryNo === sourceInquiryNo)
      const handoffs = store.listHandoffs()
      const records = preparations.map(preparation => {
        const context = contexts.find(item => item.sourceObjectId === preparation.recommendationPreparationNo) || null
        const decision = context ? decisions.find(item => item.decisionContextNo === context.decisionContextNo) || null : null
        const state = decision?.recommendationStatus || context?.recommendationStatus || 'comparison_ready'
        return Object.freeze({ recommendationPreparationNo: preparation.recommendationPreparationNo,
          comparisonPreparationNo: preparation.comparisonPreparationNo,
          sourceQuoteComparisonId: preparation.sourceQuoteComparisonId || preparation.comparisonPreparationNo,
          sourceInquiryNo: preparation.sourceInquiryNo, sourceRequestNo: preparation.sourceRequestNo,
          comparisonCount: preparation.comparisons.length,
          supplierCount: new Set(preparation.comparisons.map(item => item.supplierCode)).size,
          materialCount: new Set(preparation.comparisons.map(item => item.materialCode)).size,
          recommendationStatus: state, statusLabel: resolveSupplierRecommendationStatusLabelV1142811(state),
          factScope: preparation.factScope || 'runtime_fact', readOnly: preparation.readOnly === true,
          preparation, context, decision })
      })
      return Object.freeze({ providerCode: this.providerCode, factSource: this.factSource,
        upstreamFactSource: this.upstreamFactSource, records: Object.freeze(records),
        contexts: Object.freeze(contexts), approvalContexts: Object.freeze(approvalContexts),
        decisions: Object.freeze(decisions), handoffs: Object.freeze(handoffs), recordCount: records.length,
        current: records.at(-1) || null,
        emptyMessage: records.length ? '' : '暂无已完成的报价比较数据。' })
    },
  })
}

export const supplierRecommendationProviderV1142811 = createSupplierRecommendationProviderV1142811()
