import { createSupplierRecommendationProviderV1142811 } from './supplierRecommendationProviderV1142811.js'
import { priceReferenceProvider } from './priceReferenceProvider.js'
import { supplierCandidateProvider } from './supplierCandidateProvider.js'
import { getProfitSession } from '../demo/demoMode.js'
import { quoteComparisonRuntimeStoreV1142810 } from '../runtime/quoteComparisonRuntimeStoreV1142810.js'
import { SUPPLIER_RECOMMENDATION_READ_ONLY_QUOTE_COMPARISON_FACTS_V1142811 } from '../acceptance/supplierRecommendationQuoteComparisonTestFactsV1142811.js'
import { priceApprovalSupplierRecommendationHandoffStoreV11428161 } from '../process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { createRecommendationConfirmationContextV1142816,
  createSupplierRecommendationDecisionContextV1142816 } from '../process/scm/supplierRecommendation/supplierRecommendationDecisionDomainV1142816.js'
import { createSupplierRecommendationRuntimeContextV11428163 } from '../process/scm/supplierRecommendation/supplierRecommendationRuntimeContextV11428163.js'

export const SUPPLIER_RECOMMENDATION_DECISION_PROVIDER_VERSION_V1142816 = 'V1.14.2.8.18.16'

export function createSupplierRecommendationRealFactSourceV11428161({
  priceApprovalHandoffStore = priceApprovalSupplierRecommendationHandoffStoreV11428161,
  quoteComparisonStore = quoteComparisonRuntimeStoreV1142810,
  acceptanceFacts = SUPPLIER_RECOMMENDATION_READ_ONLY_QUOTE_COMPARISON_FACTS_V1142811,
  acceptanceModeResolver = () => getProfitSession().demoMode === true,
} = {}) {
  return Object.freeze({
    sourceCode: 'SCM_SUPPLIER_RECOMMENDATION_REAL_FACT_SOURCE',
    listRecommendationPreparations() {
      const priceApprovalPreparations = priceApprovalHandoffStore.listPreparations()
      const existing = new Set(priceApprovalPreparations.map(item => item.recommendationPreparationNo))
      const quoteComparisonPreparations = quoteComparisonStore.listRecommendationPreparations()
        .filter(item => !existing.has(item.recommendationPreparationNo))
      const realFacts = [...priceApprovalPreparations, ...quoteComparisonPreparations]
      if (realFacts.length) return Object.freeze(realFacts)
      return acceptanceModeResolver() ? Object.freeze([...acceptanceFacts]) : Object.freeze([])
    },
  })
}

export const supplierRecommendationRealFactSourceV11428161 =
  createSupplierRecommendationRealFactSourceV11428161()

export function createSupplierRecommendationDecisionProviderV1142816({
  realFactSource = supplierRecommendationRealFactSourceV11428161,
  quoteComparisonProvider = createSupplierRecommendationProviderV1142811({ sourceStore: realFactSource }),
  priceReferenceContextProvider = priceReferenceProvider,
  supplierQualificationProvider = supplierCandidateProvider,
} = {}) {
  return Object.freeze({
    providerCode: 'SupplierRecommendationDecisionProvider',
    inputObjects: Object.freeze(['QuoteComparison', 'PriceReferenceContext', 'SupplierQualificationContext']),
    readOnlyEvidence: true,
    load(options = {}) {
      const base = quoteComparisonProvider.load(options)
      const supplierQualificationFacts = supplierQualificationProvider.load().options || []
      const records = base.records.map(record => {
        const runtimeContext = record.preparation.priceApprovalId
          ? createSupplierRecommendationRuntimeContextV11428163({ preparation: record.preparation },
            record.preparation.createdAt)
          : null
        const currentQuotes = record.preparation.comparisons.map(comparison => ({
          inquiryNo: record.sourceInquiryNo,
          materialCode: comparison.materialCode,
          materialName: comparison.materialName,
          supplierCode: comparison.supplierCode,
          supplierName: comparison.supplierName,
          quotePrice: comparison.unitPrice,
          comparisonResult: comparison.comparisonResult,
        }))
        const priceFacts = record.preparation.priceReferenceRecords?.length
          ? { records: record.preparation.priceReferenceRecords }
          : priceReferenceContextProvider.load({ currentQuotes })
        const recommendationContext = createSupplierRecommendationDecisionContextV1142816({
          preparation: record.preparation,
          runtimeContext: record.context,
          priceReferenceRecords: priceFacts.records,
          supplierQualificationFacts,
        })
        const approval = base.approvalContexts.find(item =>
          item.decisionContextNo === record.context?.decisionContextNo) || {}
        return Object.freeze({
          ...record,
          priceApprovalId: record.preparation.priceApprovalId || '',
          priceApprovalNo: record.preparation.priceApprovalNo || record.preparation.priceApprovalId || '',
          quoteComparisonId: record.preparation.quoteComparisonId
            || record.preparation.sourceQuoteComparisonId || record.comparisonPreparationNo,
          runtimeContext,
          entryKey: runtimeContext?.entryKey || '',
          recommendationContext,
          recommendationEvidence: recommendationContext.recommendationEvidence,
          priceReferenceContexts: Object.freeze(priceFacts.records),
          recommendationConfirmationContext: createRecommendationConfirmationContextV1142816(approval),
        })
      })
      return Object.freeze({
        ...base,
        providerCode: this.providerCode,
        upstreamProviderCode: base.providerCode,
        upstreamFactSource: 'PriceApprovalHandoff|QuoteComparisonRuntimeStore',
        inputObjects: this.inputObjects,
        records: Object.freeze(records),
        current: records.at(-1) || null,
        recordCount: records.length,
        businessWriteCount: 0,
        productionDataWritten: false,
        automaticDecisionCount: 0,
      })
    },
  })
}

export const supplierRecommendationDecisionProviderV1142816 =
  createSupplierRecommendationDecisionProviderV1142816()
