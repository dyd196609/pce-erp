export const SUPPLIER_QUOTE_DOMAIN_VERSION = 'V1.14.2.8.18.9'

const text = value => String(value ?? '').trim()
const number = value => Number(value || 0)
const clone = value => JSON.parse(JSON.stringify(value))

function normalizeMaterial(line = {}, index = 0) {
  return Object.freeze({
    lineNo: line.lineNo ?? index + 1,
    materialCode: text(line.materialCode),
    materialName: text(line.materialName),
    specification: text(line.specification),
    quantity: number(line.quantity),
    requiredDate: text(line.requiredDate),
  })
}

function normalizeSupplier(candidate = {}) {
  return Object.freeze({
    supplierCode: text(candidate.supplierCode || candidate.supplierId || candidate.id),
    supplierName: text(candidate.supplierName || candidate.name),
  })
}

export function buildMaterialSupplierCombinations(preparation = {}) {
  const materialLines = (preparation.materialLines || []).map(normalizeMaterial)
  const suppliers = (preparation.supplierCandidates || []).map(normalizeSupplier)
  const materialSuppliers = preparation.materialSupplierCandidates || []
  const combinations = materialSuppliers.length
    ? materialSuppliers.map(item => {
      const sourceLine = materialLines.find(line => line.materialCode === text(item.materialCode)) || {}
      return {
        ...normalizeMaterial({ ...sourceLine, ...item }),
        ...normalizeSupplier(item),
      }
    })
    : materialLines.flatMap(line => suppliers.map(supplier => ({ ...line, ...supplier })))
  return Object.freeze(combinations.map(item => Object.freeze(item)))
}

export function createSupplierQuoteContextModel(preparation = {}, now = new Date().toISOString()) {
  const materialLines = Object.freeze((preparation.materialLines || []).map(normalizeMaterial))
  const supplierCandidates = Object.freeze((preparation.supplierCandidates || []).map(normalizeSupplier))
  const materialSupplierCandidates = buildMaterialSupplierCombinations(preparation)
  const quotePreparationNo = text(preparation.quotePreparationNo)
  if (!quotePreparationNo || !text(preparation.inquiryNo) || !materialLines.length || !materialSupplierCandidates.length) {
    throw new Error('SUPPLIER_QUOTE_CONTEXT_SOURCE_INCOMPLETE')
  }
  if (materialLines.some(line => !line.materialCode || !line.materialName || line.quantity <= 0)
    || materialSupplierCandidates.some(item => !item.materialCode || !item.supplierCode || !item.supplierName)) {
    throw new Error('SUPPLIER_QUOTE_CONTEXT_FIELD_INCOMPLETE')
  }
  return Object.freeze({
    objectType: 'SupplierQuoteContext',
    supplierQuoteContextNo: `SQC-${quotePreparationNo}`,
    quotePreparationNo,
    inquiryNo: text(preparation.inquiryNo),
    sourceRequestNo: text(preparation.sourceRequestNo),
    supplierCandidates,
    materialLines,
    materialSupplierCandidates,
    quotationDeadline: text(preparation.quotationDeadline || preparation.deadline
      || preparation.materialLines?.[0]?.requiredDate),
    quoteStatus: 'quote_preparation_ready',
    createdAt: now,
    updatedAt: now,
    supplierApiCalled: false,
    supplierSent: false,
    quoteComparisonCreated: false,
    purchaseOrderCreated: false,
    financeCreated: false,
  })
}

export function createSupplierQuoteModel(input = {}, context = {}, now = new Date().toISOString()) {
  const supplierCode = text(input.supplierCode)
  const materialCode = text(input.materialCode)
  const combination = context.materialSupplierCandidates?.find(item =>
    item.materialCode === materialCode && item.supplierCode === supplierCode)
  if (!combination) throw new Error('SUPPLIER_QUOTE_COMBINATION_NOT_ALLOWED')
  const quote = {
    objectType: 'SupplierQuote',
    quoteNo: text(input.quoteNo) || `SQ-${context.inquiryNo}-${materialCode}-${supplierCode}`,
    supplierQuoteContextNo: context.supplierQuoteContextNo,
    quotePreparationNo: context.quotePreparationNo,
    inquiryNo: context.inquiryNo,
    sourceRequestNo: context.sourceRequestNo,
    supplierCode,
    supplierName: text(input.supplierName || combination.supplierName),
    materialCode,
    materialName: text(input.materialName || combination.materialName),
    quantity: number(input.quantity || combination.quantity),
    unitPrice: number(input.unitPrice),
    taxRate: number(input.taxRate),
    deliveryDate: text(input.deliveryDate),
    validityDate: text(input.validityDate),
    remark: text(input.remark),
    quoteStatus: 'supplier_quote_collecting',
    createdAt: text(input.createdAt) || now,
    updatedAt: now,
    supplierApiCalled: false,
    supplierSent: false,
    quoteComparisonCreated: false,
    purchaseOrderCreated: false,
    financeCreated: false,
  }
  if (!quote.supplierName || !quote.materialName || quote.quantity <= 0 || quote.unitPrice <= 0
    || quote.taxRate < 0 || !quote.deliveryDate || !quote.validityDate) {
    throw new Error('SUPPLIER_QUOTE_REQUIRED_FIELD_INCOMPLETE')
  }
  return Object.freeze(clone(quote))
}

export function validateSupplierQuoteDomain(context = {}, quote = null) {
  const contextValid = context.objectType === 'SupplierQuoteContext'
    && ['quote_preparation_ready', 'supplier_quote_collecting', 'supplier_quote_completed', 'comparison_ready']
      .includes(context.quoteStatus)
    && Boolean(context.quotePreparationNo && context.inquiryNo)
    && Array.isArray(context.materialLines) && context.materialLines.length > 0
    && Array.isArray(context.materialSupplierCandidates) && context.materialSupplierCandidates.length > 0
  const quoteValid = !quote || (quote.objectType === 'SupplierQuote'
    && Boolean(quote.supplierCode && quote.supplierName && quote.materialCode && quote.materialName)
    && quote.quantity > 0 && quote.unitPrice > 0 && quote.taxRate >= 0
    && Boolean(quote.deliveryDate && quote.validityDate))
  return Object.freeze({ valid: contextValid && quoteValid, result: contextValid && quoteValid ? 'PASS' : 'FAIL' })
}
