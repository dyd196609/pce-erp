import { supplierQuoteProvider } from '../providers/supplierQuoteProviderV114289.js'

export const SUPPLIER_QUOTE_QUOTE_COMPARISON_RUNTIME_ADAPTER_VERSION = 'V1.14.2.8.18.12'

export function createSupplierQuoteQuoteComparisonRuntimeAdapter({ sourceProvider = supplierQuoteProvider } = {}) {
  return Object.freeze({
    adapterCode: 'SUPPLIER_QUOTE_TO_QUOTE_COMPARISON_RUNTIME_ADAPTER',
    inputObject: 'SupplierQuote', outputObject: 'QuoteComparisonContext',
    readOnly: true, productionWriteAllowed: false,
    load({ inquiryNo = '' } = {}) {
      const facts = sourceProvider.load({ inquiryNo })
      const contexts = facts.contexts.map(context => {
        const records = facts.records.filter(item => item.supplierQuoteContextNo === context.supplierQuoteContextNo)
        const quotes = records.map(item => item.quote).filter(Boolean)
        const suppliers = [...new Map(records.map(item => [item.supplierCode,
          Object.freeze({ supplierCode: item.supplierCode, supplierName: item.supplierName })])).values()]
        const materials = [...new Map(records.map(item => [item.materialCode,
          Object.freeze({ materialCode: item.materialCode, materialName: item.materialName,
            quantity: item.quantity })])).values()]
        return Object.freeze({
          objectType: 'QuoteComparisonContext',
          quoteComparisonContextNo: `QCC-${context.inquiryNo}`,
          sourceInquiryId: context.inquiryNo,
          sourceRequestNo: context.sourceRequestNo,
          supplierQuoteContextNo: context.supplierQuoteContextNo,
          supplier: Object.freeze(suppliers), material: Object.freeze(materials),
          quotePrice: Object.freeze(records.map(item => Object.freeze({ supplierCode: item.supplierCode,
            materialCode: item.materialCode, quotePrice: item.quote?.unitPrice ?? null,
            currency: item.quote?.currency || 'CNY' }))),
          deliveryDate: Object.freeze(records.map(item => Object.freeze({ supplierCode: item.supplierCode,
            materialCode: item.materialCode,
            deliveryDate: item.quote?.deliveryDate || item.bindingFact?.deliveryDate || '' }))),
          validityStatus: Object.freeze(records.map(item => Object.freeze({ supplierCode: item.supplierCode,
            materialCode: item.materialCode,
            validityStatus: item.quote?.validityDate ? 'valid' : item.bindingFact?.validityStatus || 'pending' }))),
          supplierQuoteStatus: context.quoteStatus,
          sourceReady: context.quoteStatus === 'comparison_ready' && quotes.length === records.length && quotes.length > 0,
          readOnly: true, runtimeBinding: true,
          purchaseOrderCreated: false, financeCreated: false, wmsCreated: false, mesCreated: false,
          businessWriteCount: 0, productionDataWritten: 0,
        })
      })
      return Object.freeze({ adapterCode: this.adapterCode, contexts: Object.freeze(contexts),
        contextCount: contexts.length, businessWriteCount: 0, productionDataWritten: 0 })
    },
  })
}

export const supplierQuoteQuoteComparisonRuntimeAdapter = createSupplierQuoteQuoteComparisonRuntimeAdapter()
