import { supplierQuoteProvider } from './supplierQuoteProviderV114289.js'
import { quoteComparisonRuntimeStoreV1142810 } from '../runtime/quoteComparisonRuntimeStoreV1142810.js'
import { resolveQuoteComparisonStatusLabel } from '../process/scm/quoteComparison/quoteComparisonStateContractV1142810.js'
import { createSupplierQuoteQuoteComparisonRuntimeAdapter } from '../runtime/supplierQuoteQuoteComparisonRuntimeAdapterV1142812.js'

export const QUOTE_COMPARISON_PROVIDER_VERSION = 'V1.14.2.8.18.10'

function sourceForContext(context, records) {
  const supplierQuotes = records.filter(item => item.supplierQuoteContextNo === context.supplierQuoteContextNo)
    .map(item => item.quote).filter(Boolean)
  return Object.freeze({ inquiryNo: context.inquiryNo, sourceRequestNo: context.sourceRequestNo,
    materialLines: Object.freeze((context.materialLines || []).map(item => Object.freeze({ ...item }))),
    supplierQuotes: Object.freeze(supplierQuotes.map(item => Object.freeze({ ...item }))) })
}

export function createQuoteComparisonProvider({ sourceProvider = supplierQuoteProvider,
  store = quoteComparisonRuntimeStoreV1142810, runtimeAdapter = null } = {}) {
  return Object.freeze({
    providerCode: 'SCM_QUOTE_COMPARISON_PROVIDER', sourceProviderCode: 'SCM_SUPPLIER_QUOTE_PROVIDER',
    factSource: 'SupplierQuoteProvider',
    load({ inquiryNo = '' } = {}) {
      const upstream = sourceProvider.load({ inquiryNo })
      const adapter = runtimeAdapter || createSupplierQuoteQuoteComparisonRuntimeAdapter({ sourceProvider })
      const bindingFacts = adapter.load({ inquiryNo })
      const eligible = upstream.contexts.filter(item => item.quoteStatus === 'comparison_ready')
      const contexts = store.listContexts().filter(item => !inquiryNo || item.sourceInquiryNo === inquiryNo)
        .filter(item => eligible.some(source => source.inquiryNo === item.sourceInquiryNo))
      const comparisons = store.listComparisons().filter(item =>
        contexts.some(context => context.comparisonPreparationNo === item.comparisonPreparationNo))
      const records = upstream.contexts.map(source => {
        const persisted = contexts.find(item => item.sourceInquiryNo === source.inquiryNo) || null
        const sourceFacts = sourceForContext(source, upstream.records)
        const bindingContext = bindingFacts.contexts.find(item => item.supplierQuoteContextNo === source.supplierQuoteContextNo)
        const sourceReady = bindingContext?.sourceReady === true
        return Object.freeze({
          inquiryNo: source.inquiryNo, sourceRequestNo: source.sourceRequestNo,
          quoteCount: sourceFacts.supplierQuotes.length,
          supplierCount: new Set(sourceFacts.supplierQuotes.map(item => item.supplierCode)).size,
          sourceFacts, comparisonPreparationNo: persisted?.comparisonPreparationNo || '',
          runtimeBindingContext: bindingContext || null, sourceReady,
          comparisonStatus: persisted?.comparisonStatus || (sourceReady ? 'supplier_quote_completed' : 'awaiting_supplier_quote'),
          statusLabel: persisted ? resolveQuoteComparisonStatusLabel(persisted.comparisonStatus)
            : sourceReady ? resolveQuoteComparisonStatusLabel('supplier_quote_completed') : '等待供应商报价完成',
        })
      })
      return Object.freeze({ providerCode: this.providerCode, sourceProviderCode: this.sourceProviderCode,
        factSource: this.factSource, records: Object.freeze(records), contexts: Object.freeze(contexts),
        comparisons: Object.freeze(comparisons), recordCount: records.length,
        comparisonCount: comparisons.length, current: records.at(-1) || null,
        bindingContexts: bindingFacts.contexts,
        businessWriteCount: 0, productionDataWritten: 0,
        emptyMessage: records.length ? '' : '暂无已完成的供应商报价数据。' })
    },
  })
}

export const quoteComparisonProviderV1142810 = createQuoteComparisonProvider()
