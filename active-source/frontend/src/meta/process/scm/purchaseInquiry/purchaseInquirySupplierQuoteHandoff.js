import { normalizePurchaseInquirySupplierCandidate } from './purchaseInquirySupplierCandidateContext.js'
import { buildMaterialSupplierCandidates } from './materialSupplierCandidateContext.js'

export const PURCHASE_INQUIRY_SUPPLIER_QUOTE_HANDOFF = Object.freeze({
  handoffCode: 'PURCHASE_INQUIRY_TO_QUOTE_PREPARATION',
  sourceObject: 'PurchaseInquiry', targetObject: 'QuotePreparationContext',
  transferredFields: Object.freeze(['inquiryNo', 'sourceRequestNo', 'materialLines', 'materialSupplierCandidates']),
  supplierQuoteCreated: false,
})

export function createPurchaseInquirySupplierQuoteHandoff(inquiry = {}) {
  const materialLines = (inquiry.materialLines || inquiry.lines || []).map(line => Object.freeze({
    materialCode: line.materialCode, materialName: line.materialName,
    specification: line.specification || '', quantity: Number(line.quantity || 0),
    requiredDate: line.requiredDate || '',
  }))
  const supplierCandidates = (inquiry.supplierCandidates || inquiry.suppliers || [])
    .map(normalizePurchaseInquirySupplierCandidate)
  const materialSupplierCandidates = buildMaterialSupplierCandidates(materialLines.map((line, index) => ({
    ...line,
    supplierCandidates: (inquiry.materialLines || inquiry.lines || [])[index]?.supplierCandidates,
  })), supplierCandidates)
  const context = Object.freeze({ objectType: 'QuotePreparationContext', contextType: 'quote_preparation_context',
    quotePreparationNo: `QPC-${inquiry.inquiryNo}`, inquiryNo: inquiry.inquiryNo,
    sourceRequestNo: inquiry.sourceRequestNo || '', materialLines: Object.freeze(materialLines),
    materialSupplierCandidates,
    supplierCandidates: Object.freeze(supplierCandidates), preparationStatus: 'quote_preparation_ready',
    supplierQuoteCreated: false, supplierSent: false, purchaseOrderCreated: false, productionDataWritten: false })
  const valid = Boolean(context.inquiryNo) && context.materialLines.length > 0
    && context.materialLines.every(line => line.materialCode && line.materialName && line.quantity > 0)
    && context.materialSupplierCandidates.length > 0
    && context.materialLines.every(line => context.materialSupplierCandidates
      .some(candidate => candidate.materialCode === line.materialCode))
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid, context,
    contract: PURCHASE_INQUIRY_SUPPLIER_QUOTE_HANDOFF })
}
