import { quoteComparisonSimpleProvider } from './quoteComparisonSimpleProviderV11428121.js'

export const PRICE_APPROVAL_FROM_QUOTE_COMPARISON_PROVIDER_VERSION = 'V1.14.2.8.18.12.1'

export function createPriceApprovalFromQuoteComparisonProvider({ sourceProvider = quoteComparisonSimpleProvider } = {}) {
  return Object.freeze({
    providerCode: 'SCM_PRICE_APPROVAL_PREPARATION_PROVIDER', factSource: 'QuoteComparison',
    load(query = {}) {
      const source = sourceProvider.load(query)
      const contexts = source.records.map((comparison, index) => Object.freeze({
        objectType: 'PriceApprovalPreparationContext',
        priceApprovalPreparationNo: `PAP-${comparison.sourceInquiryId}-${index + 1}`,
        priceApprovalId: `PAP-${comparison.sourceInquiryId}-${index + 1}`,
        priceApprovalNo: `PAP-${comparison.sourceInquiryId}-${index + 1}`,
        quoteComparisonId: comparison.quoteComparisonId,
        inquiryNo: comparison.sourceInquiryId, sourceInquiryId: comparison.sourceInquiryId,
        sourceRequestNo: comparison.sourceRequestNo, materialCode: comparison.materialCode,
        materialName: comparison.materialName, supplierQuotes: comparison.supplierQuotes,
        quoteComparisonResult: comparison,
        lowestQuote: comparison.lowestQuote, preparationStatus: 'price_approval_preparation_ready',
        sourceObjectType: 'QuoteComparison', automaticApprovalCreated: false,
        purchaseOrderCreated: false, financeCreated: false,
      }))
      return Object.freeze({ providerCode: this.providerCode, factSource: this.factSource,
        contexts: Object.freeze(contexts), resultCount: contexts.length, current: contexts.at(-1) || null,
        businessWriteCount: 0, productionDataWritten: 0, supplierQuoteCreated: false,
        quoteComparisonCreated: false, purchaseOrderCreated: false, financeCreated: false,
        emptyMessage: contexts.length ? '' : '暂无报价比较数据' })
    },
  })
}

export const priceApprovalFromQuoteComparisonProvider = createPriceApprovalFromQuoteComparisonProvider()
