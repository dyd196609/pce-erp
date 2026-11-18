import { supplierQuoteProvider } from './supplierQuoteProviderV114289.js'
import { createQuoteComparisonSimpleRows } from '../process/scm/quoteComparison/quoteComparisonSimpleModelV11428121.js'
import { resolveEnterpriseListCanaryQuery } from '../runtime/enterpriseListCanaryMode.js'

const loadCanaryApi = () => import('../../api/purchaseCanary.js')

export const QUOTE_COMPARISON_SIMPLE_PROVIDER_VERSION = 'V1.14.2.8.4.23'

export function createQuoteComparisonSimpleProvider({ sourceProvider = supplierQuoteProvider } = {}) {
  return Object.freeze({
    providerCode: 'SCM_QUOTE_COMPARISON_SIMPLE_PROVIDER', factSource: 'SCM_SUPPLIER_QUOTE_PROVIDER',
    load(query = {}) {
      const source = sourceProvider.load(query)
      const readyContextNos = new Set(source.contexts.filter(item => item.quoteStatus === 'comparison_ready')
        .map(item => item.supplierQuoteContextNo))
      const sourceRecords = source.records.filter(item => readyContextNos.has(item.supplierQuoteContextNo))
      const records = createQuoteComparisonSimpleRows(sourceRecords)
      return Object.freeze({ providerCode: this.providerCode, factSource: this.factSource,
        records, recordCount: records.length, sourceQuoteCount: sourceRecords.length,
        current: records.at(-1) || null, businessWriteCount: 0, productionDataWritten: 0,
        supplierRecommendationCreated: false, purchaseOrderCreated: false })
    },
    async loadRuntime({ query = {} } = {}) {
      const canary = resolveEnterpriseListCanaryQuery(query)
      if (!canary.isCanaryMode) {
        const facts = this.load()
        return Object.freeze({ ...facts, rows: facts.records, resultCount: facts.recordCount,
          source: 'production', dataMode: 'production', factLoadStatus: 'loaded',
          canaryApiCallCount: 0, productionProviderCallCount: 1, productionUserDataWritten: false })
      }
      const { getQuoteComparisonCanaryRuntime } = await loadCanaryApi()
      const response = await getQuoteComparisonCanaryRuntime({ canaryBatchId: canary.canaryBatchId,
        scenarioCode: canary.scenarioCode })
      if (!response?.success || !response.data) throw new Error(response?.error?.message || '报价比较金丝雀事实读取失败')
      return Object.freeze({ providerCode: 'SCM_QUOTE_COMPARISON_CANARY_PROVIDER', factSource: 'server',
        records: Object.freeze((response.data.records || []).map(row => Object.freeze({ ...row }))),
        recordCount: response.data.recordCount || 0, current: response.data.records?.at(-1) || null,
        rows: Object.freeze((response.data.records || []).map(row => Object.freeze({ ...row }))),
        resultCount: response.data.recordCount || 0, source: 'canary',
        dataMode: 'canary_acceptance', canaryBatchId: response.data.canaryBatchId,
        scenarioCode: response.data.scenarioCode, sourceMapping: response.data.sourceMapping,
        factLoadStatus: 'loaded',
        canaryApiCallCount: 1, productionProviderCallCount: 0, businessWriteCount: 0,
        productionDataWritten: 0, productionUserDataWritten: false,
        supplierRecommendationCreated: false, priceApprovalCreated: false, purchaseOrderCreated: false })
    },
  })
}

export const quoteComparisonSimpleProvider = createQuoteComparisonSimpleProvider()
