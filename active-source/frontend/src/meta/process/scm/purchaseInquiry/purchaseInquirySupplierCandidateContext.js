export const PURCHASE_INQUIRY_SUPPLIER_CANDIDATE_CONTEXT_VERSION = 'V1.14.2.8.18.7-SUPPLEMENT'

export function normalizePurchaseInquirySupplierCandidate(candidate = {}) {
  const source = typeof candidate === 'string'
    ? { supplierCode: candidate, supplierName: candidate }
    : candidate
  return Object.freeze({
    supplierCode: String(source.supplierCode || source.code || source.supplierId || source.id || ''),
    supplierName: String(source.supplierName || source.name || source.label || ''),
    supplierStatus: String(source.supplierStatus || source.status || source.businessStatus || 'active'),
    supplierCategory: String(source.supplierCategory || source.category || source.supplierType || 'unclassified'),
    source: String(source.source || 'Supplier Master'),
  })
}

export function createPurchaseInquirySupplierCandidateContext(candidates = []) {
  return Object.freeze({
    objectType: 'PurchaseInquirySupplierCandidateContext',
    providerCode: 'SupplierCandidateProvider',
    source: 'Supplier Master Provider',
    allowFreeText: false,
    candidates: Object.freeze(candidates.map(normalizePurchaseInquirySupplierCandidate)),
  })
}

export function addPurchaseInquirySupplierCandidate(candidates = [], candidate = {}) {
  const normalized = normalizePurchaseInquirySupplierCandidate(candidate)
  if (!normalized.supplierCode || !normalized.supplierName) throw new Error('SUPPLIER_MASTER_SELECTION_REQUIRED')
  if (candidates.some(item => normalizePurchaseInquirySupplierCandidate(item).supplierCode === normalized.supplierCode)) {
    throw new Error('SUPPLIER_CANDIDATE_ALREADY_EXISTS')
  }
  return [...candidates.map(normalizePurchaseInquirySupplierCandidate), normalized]
}

export function removePurchaseInquirySupplierCandidate(candidates = [], index) {
  return candidates.filter((_, candidateIndex) => candidateIndex !== index)
    .map(normalizePurchaseInquirySupplierCandidate)
}

export function replacePurchaseInquirySupplierCandidate(candidates = [], index, candidate = {}) {
  const normalized = normalizePurchaseInquirySupplierCandidate(candidate)
  if (!normalized.supplierCode || !normalized.supplierName) throw new Error('SUPPLIER_MASTER_SELECTION_REQUIRED')
  if (candidates.some((item, candidateIndex) => candidateIndex !== index
    && normalizePurchaseInquirySupplierCandidate(item).supplierCode === normalized.supplierCode)) {
    throw new Error('SUPPLIER_CANDIDATE_ALREADY_EXISTS')
  }
  return candidates.map((item, candidateIndex) => candidateIndex === index
    ? normalized : normalizePurchaseInquirySupplierCandidate(item))
}

export function validatePurchaseInquirySupplierCandidateContext(context = {}) {
  const candidates = context.candidates || []
  const valid = context.objectType === 'PurchaseInquirySupplierCandidateContext'
    && context.allowFreeText === false && candidates.length > 0
    && candidates.every(candidate => ['supplierCode', 'supplierName', 'supplierStatus', 'supplierCategory', 'source']
      .every(field => Boolean(candidate[field])))
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
