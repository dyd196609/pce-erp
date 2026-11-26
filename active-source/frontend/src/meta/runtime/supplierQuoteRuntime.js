export const SUPPLIER_QUOTE_RUNTIME_VERSION = 'V1.14.2.8.11'

const contexts = []
const quotes = []
const text = value => String(value ?? '').trim()

function candidateId(candidate) {
  return text(candidate?.supplierId || candidate?.supplierCode || candidate?.id || candidate)
}

function normalizeMaterial(line = {}, index = 0) {
  return Object.freeze({
    lineNo: line.lineNo ?? index + 1,
    materialCode: text(line.materialCode),
    materialName: text(line.materialName),
    quantity: Number(line.quantity || 0),
    unit: text(line.unit),
  })
}

export function createSupplierQuoteContext(inquiry = {}) {
  const materials = Object.freeze((inquiry.lines || []).map(normalizeMaterial))
  const supplierCandidates = Object.freeze((inquiry.suppliers || inquiry.supplierCandidates || []).map(candidate => Object.freeze({
    supplierId: candidateId(candidate),
    supplierName: text(candidate?.supplierName || candidate?.name || candidateId(candidate)),
  })))
  const deadline = text(inquiry.responseDeadline || inquiry.deadline || inquiry.validUntil)
  if (!text(inquiry.inquiryNo) || !materials.length || materials.some(item => !item.materialCode || item.quantity <= 0)) {
    throw new Error('询价编号、物料和数量不能为空')
  }
  if (!supplierCandidates.length || supplierCandidates.some(item => !item.supplierId)) throw new Error('供应商候选不能为空')
  if (!deadline) throw new Error('报价截止日期不能为空')
  const existing = contexts.find(item => item.inquiryNo === inquiry.inquiryNo)
  if (existing) return existing
  const context = Object.freeze({
    contextCode: `SQC-${inquiry.inquiryNo}`,
    objectType: 'SupplierQuoteContext',
    inquiryNo: inquiry.inquiryNo,
    materials,
    supplierCandidates,
    deadline,
    status: 'quote_context_created',
    supplierApiCalled: false,
    quoteComparisonCreated: false,
    purchaseOrderCreated: false,
    paymentCreated: false,
    productionDataWritten: false,
  })
  contexts.push(context)
  return context
}

export function markSupplierQuoteWaiting(context = {}) {
  if (context.status !== 'quote_context_created') throw new Error('报价上下文状态不允许进入等待报价')
  const waiting = Object.freeze({ ...context, status: 'waiting_supplier_quote' })
  const index = contexts.findIndex(item => item.contextCode === context.contextCode)
  if (index >= 0) contexts.splice(index, 1, waiting)
  return waiting
}

export function receiveSupplierQuote(context = {}, input = {}) {
  if (context.status !== 'waiting_supplier_quote') throw new Error('报价上下文尚未进入等待状态')
  const supplierId = candidateId(input.supplierId || input.supplierCode)
  if (!context.supplierCandidates.some(item => item.supplierId === supplierId)) throw new Error('报价供应商不在候选范围')
  const lines = Object.freeze((input.lines || []).map((line, index) => Object.freeze({
    ...normalizeMaterial(line, index),
    unitPrice: Number(line.unitPrice || 0),
    taxRate: Number(line.taxRate || 0),
    deliveryDate: text(line.deliveryDate),
  })))
  if (!lines.length || lines.some(line => !line.materialCode || line.quantity <= 0)) throw new Error('报价物料与数量不能为空')
  const quote = Object.freeze({
    objectType: 'SupplierQuote',
    quoteNo: text(input.quoteNo) || `SQ-${context.inquiryNo}-${supplierId}`,
    contextCode: context.contextCode,
    inquiryNo: context.inquiryNo,
    supplierId,
    quoteDate: text(input.quoteDate),
    currency: text(input.currency || 'CNY'),
    validUntil: text(input.validUntil || context.deadline),
    lines,
    status: 'quotation_received',
    sourceMode: 'manual_receive',
    supplierApiCalled: false,
    quoteComparisonCreated: false,
    purchaseOrderCreated: false,
    paymentCreated: false,
    productionDataWritten: false,
  })
  quotes.push(quote)
  return quote
}

export function saveSupplierQuote(quote = {}) {
  if (quote.status !== 'quotation_received') throw new Error('仅已接收报价允许保存')
  if (!quote.quoteDate || !quote.validUntil || !quote.currency) throw new Error('报价日期、有效期和币种不能为空')
  if (!quote.lines?.length || quote.lines.some(line => line.unitPrice <= 0 || !line.deliveryDate)) {
    throw new Error('报价单价和交付日期不能为空')
  }
  const completed = Object.freeze({
    ...quote,
    status: 'quotation_completed',
    comparisonReadinessStatus: 'comparison_ready',
    quoteComparisonCreated: false,
    supplierApiCalled: false,
    purchaseOrderCreated: false,
    paymentCreated: false,
    productionDataWritten: false,
    persistenceMode: 'session_runtime',
  })
  const index = quotes.findIndex(item => item.quoteNo === quote.quoteNo)
  if (index >= 0) quotes.splice(index, 1, completed)
  return Object.freeze({
    result: 'PASS',
    saved: true,
    object: completed,
    businessWriteCount: 1,
    productionDataWritten: false,
  })
}

export function listSupplierQuoteContexts() {
  return Object.freeze([...contexts])
}

export function listSupplierQuotes() {
  return Object.freeze([...quotes])
}

