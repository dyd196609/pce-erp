import { quotePreparationProvider } from './quotePreparationProvider.js'
import { createPriceApprovalPreparationContext } from '../process/scm/purchaseInquiry/priceApprovalPreparationContext.js'
import { priceApprovalFromQuoteComparisonProvider } from './priceApprovalFromQuoteComparisonProviderV11428121.js'

export const PRICE_APPROVAL_PREPARATION_PROVIDER_VERSION = 'V1.14.2.8.18.8'

export function createPriceApprovalPreparationProvider({ quoteProvider = quotePreparationProvider,
  comparisonProvider = priceApprovalFromQuoteComparisonProvider } = {}) {
  return Object.freeze({
    providerCode: 'SCM_PRICE_APPROVAL_PREPARATION_PROVIDER',
    factSource: 'current_quote_preparation_context_only',
    legacyDataEnabled: false,
    load(query = {}) {
      const comparisonFacts = comparisonProvider.load(query)
      if (comparisonFacts.resultCount) return comparisonFacts
      const quoteFacts = quoteProvider.load(query)
      const contexts = quoteFacts.records.map(createPriceApprovalPreparationContext)
      return Object.freeze({
        providerCode: this.providerCode,
        factSource: this.factSource,
        legacyDataEnabled: false,
        contexts: Object.freeze(contexts),
        resultCount: contexts.length,
        current: contexts.at(-1) || null,
        emptyMessage: contexts.length ? '' : '暂无报价准备数据',
        supplierQuoteCreated: false,
        quoteComparisonCreated: false,
        purchaseOrderCreated: false,
        financeCreated: false,
      })
    },
  })
}

export const priceApprovalPreparationProvider = createPriceApprovalPreparationProvider()
