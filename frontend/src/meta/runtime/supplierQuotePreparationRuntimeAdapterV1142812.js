import { quotePreparationProvider } from '../providers/quotePreparationProvider.js'
import { createSupplierQuoteContextModel } from '../process/scm/supplierQuote/supplierQuoteDomainModelV114289.js'

export const SUPPLIER_QUOTE_PREPARATION_RUNTIME_ADAPTER_VERSION = 'V1.14.2.8.18.12'

export function createSupplierQuotePreparationRuntimeAdapter({ preparationProvider = quotePreparationProvider } = {}) {
  return Object.freeze({
    adapterCode: 'SUPPLIER_QUOTE_PREPARATION_RUNTIME_ADAPTER',
    inputObjects: Object.freeze(['PurchaseInquiry', 'QuotePreparationContext']),
    outputObject: 'SupplierQuote',
    readOnly: true,
    productionWriteAllowed: false,
    load({ inquiryNo = '' } = {}) {
      const preparations = preparationProvider.load({ inquiryNo }).records
      const contexts = []
      const supplierQuotes = []
      for (const preparation of preparations) {
        try {
          const context = createSupplierQuoteContextModel(preparation)
          const bindingContext = Object.freeze({ ...context, sourceInquiryId: context.inquiryNo,
            quoteStatus: 'supplier_quote_collecting', runtimeBinding: true, readOnly: true,
            businessWriteCount: 0, productionDataWritten: 0 })
          contexts.push(bindingContext)
          supplierQuotes.push(...bindingContext.materialSupplierCandidates.map((pair, index) => Object.freeze({
            objectType: 'SupplierQuote',
            quoteNo: `SQ-PENDING-${bindingContext.inquiryNo}-${index + 1}`,
            supplierQuoteContextNo: bindingContext.supplierQuoteContextNo,
            quotePreparationNo: bindingContext.quotePreparationNo,
            sourceInquiryId: bindingContext.inquiryNo,
            inquiryNo: bindingContext.inquiryNo,
            sourceRequestNo: bindingContext.sourceRequestNo,
            supplierCode: pair.supplierCode, supplierName: pair.supplierName,
            materialCode: pair.materialCode, materialName: pair.materialName,
            quantity: pair.quantity, quotePrice: null, unitPrice: null,
            deliveryDate: pair.requiredDate || '', validityStatus: 'pending', validityDate: '',
            quoteStatus: 'awaiting_supplier_quote', runtimeBinding: true, readOnly: true,
            purchaseOrderCreated: false, financeCreated: false, wmsCreated: false, mesCreated: false,
          })))
        } catch { /* invalid preparations remain visible through the preparation provider error boundary */ }
      }
      return Object.freeze({ adapterCode: this.adapterCode, readOnly: true,
        contexts: Object.freeze(contexts), supplierQuotes: Object.freeze(supplierQuotes),
        contextCount: contexts.length, quoteFactCount: supplierQuotes.length,
        businessWriteCount: 0, productionDataWritten: 0 })
    },
  })
}

export const supplierQuotePreparationRuntimeAdapter = createSupplierQuotePreparationRuntimeAdapter()
