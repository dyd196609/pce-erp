import { createPriceApprovalPreparation, getPriceApprovalPreparations,
  transitionPriceApprovalPreparation } from '@/api/scmStandardPageFacts.js'
import { getPriceApprovalCanaryRuntime } from '@/api/purchaseCanary.js'
import { resolveEnterpriseListCanaryQuery } from '@/meta/runtime/enterpriseListCanaryMode.js'

export const PRICE_APPROVAL_RUNTIME_PROVIDER_VERSION = 'V1.14.2.8.4.24'

const freezeRows = rows => Object.freeze((rows || []).map(row => Object.freeze({ ...row })))

export function createPriceApprovalRuntimeProvider({ productionLoader = getPriceApprovalPreparations,
  canaryLoader = getPriceApprovalCanaryRuntime, createLoader = createPriceApprovalPreparation,
  transitionLoader = transitionPriceApprovalPreparation } = {}) {
  return Object.freeze({
    providerCode: 'SCM_PRICE_APPROVAL_RUNTIME_PROVIDER_V1142824',
    async loadRuntime(query = {}) {
      const canary = resolveEnterpriseListCanaryQuery(query)
      const response = canary.isCanaryMode
        ? await canaryLoader({ canaryBatchId: canary.canaryBatchId, scenarioCode: canary.scenarioCode })
        : await productionLoader()
      if (!response?.success || !response.data) {
        return Object.freeze({ providerCode: this.providerCode, records: Object.freeze([]), resultCount: 0,
          dataMode: canary.isCanaryMode ? 'canary_acceptance' : 'production',
          factSource: 'QuoteComparisonFact', factLoadStatus: 'blocked',
          errorCode: response?.error?.code || 'PRICE_APPROVAL_FACT_LOAD_FAILED',
          errorMessage: response?.error?.message || '采购核价事实读取失败',
          availableComparisons: Object.freeze([]), availableComparisonCount: 0,
          businessWriteCount: 0, productionUserDataWritten: false,
          supplierRecommendationCreated: false, purchaseOrderCreated: false })
      }
      const records = freezeRows(response.data.records || [])
      const availableComparisons = freezeRows(response.data.availableComparisons || [])
      return Object.freeze({ providerCode: this.providerCode, records, resultCount: records.length,
        availableComparisons, availableComparisonCount: availableComparisons.length,
        current: records.at(-1) || null, dataMode: response.data.dataMode || 'production',
        factSource: 'QuoteComparisonFact', factLoadStatus: 'loaded',
        canaryBatchId: response.data.canaryBatchId || '', scenarioCode: response.data.scenarioCode || '',
        sourceMapping: response.data.sourceMapping || null, businessWriteCount: 0,
        productionUserDataWritten: false, supplierRecommendationCreated: false, purchaseOrderCreated: false })
    },
    async createFromComparison(comparison = {}) {
      return createLoader(comparison.projectionId
        ? { sourceProjectionId: comparison.projectionId }
        : { sourceComparisonNo: comparison.quoteComparisonNo })
    },
    async transition(preparationId, input) {
      return transitionLoader(preparationId, input)
    },
  })
}

export const priceApprovalRuntimeProvider = createPriceApprovalRuntimeProvider()
