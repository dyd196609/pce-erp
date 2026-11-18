import { getScmState } from '../scm/scmStore.js'
import { createMaterialPriceContext } from '../process/scm/priceApproval/materialPriceContext.js'

export const PRICE_REFERENCE_PROVIDER_VERSION = 'V1.14.2.8.18.15'

function loadPurchaseHistory() {
  const state = getScmState()
  const orders = new Map((state.purchaseOrders || []).map(order => [String(order.id), order]))
  return (state.purchaseOrderItems || []).map(item => {
    const order = orders.get(String(item.poId)) || {}
    return Object.freeze({ materialCode: item.materialCode || item.materialId || '',
      supplierCode: item.supplierCode || item.supplierId || order.supplierCode || order.supplierId || '',
      supplierName: item.supplierName || order.supplierName || '',
      purchasePrice: Number(item.price ?? item.unitPrice ?? item.approvedPrice),
      purchaseDate: item.purchaseDate || item.orderDate || order.orderDate || order.createdAt || '',
      evidenceSource: 'PurchaseOrderHistory' })
  }).filter(item => item.materialCode && Number.isFinite(item.purchasePrice) && item.purchasePrice > 0)
}

export function createPriceReferenceProvider({ historyLoader = loadPurchaseHistory } = {}) {
  return Object.freeze({ providerCode: 'SCM_PRICE_REFERENCE_PROVIDER', readOnly: true,
    load({ currentQuotes = [] } = {}) {
      const history = historyLoader()
      const records = currentQuotes.map(quote => {
        const candidates = history.filter(item => String(item.materialCode) === String(quote.materialCode)
        ).sort((a, b) => String(b.purchaseDate).localeCompare(String(a.purchaseDate)))
        const materialPriceContext = createMaterialPriceContext({ inquiryNo: quote.inquiryNo,
          materialCode: quote.materialCode, materialName: quote.materialName,
          supplierCode: quote.supplierCode, supplierName: quote.supplierName,
          historicalPurchases: candidates, currentQuote: quote.quotePrice,
          supplierQuote: quote.quotePrice, comparisonResult: quote.comparisonResult ?? quote.rank ?? null,
          manualAssessment: quote.manualAssessment || '' })
        const context = materialPriceContext.priceReferenceContext
        return Object.freeze({ ...quote, materialPriceContext,
          materialPriceContextType: materialPriceContext.contextType,
          newMaterialPriceAssessmentContext: materialPriceContext.newMaterialPriceAssessmentContext,
          priceReferenceContext: context,
          historicalPurchasePrice: context?.historicalPurchasePrice ?? null,
          historicalLowestPurchasePrice: context?.historicalLowestPurchasePrice ?? null,
          historicalPurchaseCount: context?.historicalPurchaseCount ?? 0,
          historicalPriceList: context?.historicalPriceList ?? Object.freeze([]),
          lastPurchaseDate: context?.lastPurchaseDate || '', currentQuote: quote.quotePrice ?? null,
          priceChangeRatio: context?.priceChangeRatio ?? null,
          priceChangeEvidence: context?.priceChangeEvidence ?? null })
      })
      return Object.freeze({ providerCode: this.providerCode, records: Object.freeze(records),
        recordCount: records.length, businessWriteCount: 0, productionDataWritten: false,
        automaticDecisionCount: 0 })
    },
  })
}

export const priceReferenceProvider = createPriceReferenceProvider()
