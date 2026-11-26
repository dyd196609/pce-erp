import { listPurchaseInquiryQuotePreparationContexts } from '../runtime/purchaseInquiryNextActionRuntime.js'

export const QUOTE_PREPARATION_PROVIDER_VERSION = 'V1.14.2.8.18.7A'

export function createQuotePreparationProvider({ contextLoader = listPurchaseInquiryQuotePreparationContexts } = {}) {
  return Object.freeze({
    providerCode: 'SCM_QUOTE_PREPARATION_PROVIDER',
    factSource: 'purchase_inquiry_quote_preparation_runtime_store',
    load({ inquiryNo = '', quotePreparationNo = '' } = {}) {
      const all = contextLoader()
      const records = all.filter(item => (!inquiryNo || item.inquiryNo === inquiryNo)
        && (!quotePreparationNo || item.quotePreparationNo === quotePreparationNo))
      return Object.freeze({
        providerCode: this.providerCode, factSource: this.factSource,
        records: Object.freeze(records.map(Object.freeze)), recordCount: records.length,
        current: records.at(-1) || null,
        emptyMessage: records.length ? '' : '暂无报价准备数据。',
        supplierQuoteCreated: false,
      })
    },
  })
}

export const quotePreparationProvider = createQuotePreparationProvider()
