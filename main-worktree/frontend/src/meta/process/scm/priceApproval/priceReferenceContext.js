import { createPriceChangeEvidence } from './priceChangeEvidence.js'

export const PRICE_REFERENCE_CONTEXT_VERSION = 'V1.14.2.8.18.15'
export const PURCHASE_PRICE_DECISION_CONTEXT_VERSION = 'V1.14.2.8.4.27.2.38'

const finiteOrNull = value => Number.isFinite(Number(value)) ? Number(value) : null

export function createPriceReferenceContext(input = {}) {
  if (!input.materialCode || !input.inquiryNo) throw new Error('PRICE_REFERENCE_IDENTITY_REQUIRED')
  const history = (input.historicalPurchases || []).map(item => Object.freeze({
    purchasePrice: finiteOrNull(item.purchasePrice),
    purchaseDate: item.purchaseDate || '',
    supplierCode: item.supplierCode || '',
    supplierName: item.supplierName || '',
    evidenceSource: item.evidenceSource || input.sourceFact || 'PurchaseOrderHistory',
  })).filter(item => item.purchasePrice > 0)
    .sort((a, b) => String(b.purchaseDate).localeCompare(String(a.purchaseDate)))
  if (!history.length && finiteOrNull(input.historicalPurchasePrice) > 0) {
    history.push(Object.freeze({ purchasePrice: finiteOrNull(input.historicalPurchasePrice),
      purchaseDate: input.lastPurchaseDate || '', supplierCode: input.supplierCode || '',
      supplierName: input.supplierName || '', evidenceSource: input.sourceFact || 'PurchaseOrderHistory' }))
  }
  const latest = history[0]
  const historicalPurchasePrice = latest?.purchasePrice ?? null
  const historicalLowestPurchasePrice = history.length
    ? Math.min(...history.map(item => item.purchasePrice)) : null
  const currentQuote = finiteOrNull(input.currentQuote)
  const priceChangeRatio = historicalPurchasePrice > 0 && currentQuote != null
    ? Number(((currentQuote - historicalPurchasePrice) / historicalPurchasePrice).toFixed(4)) : null
  const priceChangeEvidence = createPriceChangeEvidence({ historyPrice: historicalPurchasePrice,
    currentPrice: currentQuote, referenceDate: latest?.purchaseDate || input.lastPurchaseDate,
    evidenceSource: latest?.evidenceSource || input.sourceFact })
  return Object.freeze({ objectType: 'PriceReferenceContext', contextMode: 'read_only_reference',
    inquiryNo: input.inquiryNo, materialCode: input.materialCode, materialName: input.materialName || '',
    supplierCode: input.supplierCode || '', historicalPurchasePrice, latestPurchasePrice: historicalPurchasePrice,
    historicalLowestPurchasePrice, lastPurchaseDate: latest?.purchaseDate || input.lastPurchaseDate || '',
    historicalPurchaseCount: history.length, historicalPriceList: Object.freeze(history),
    currentQuote, priceChangeRatio, priceChangeEvidence,
    sourceFact: input.sourceFact || 'PurchaseOrderHistory', automaticReasonablenessDecision: false,
    automaticQuoteRejection: false, automaticQuoteApproval: false,
    automaticSupplierRecommendation: false, businessStateAdvanced: false, businessWriteCount: 0 })
}

export function createPurchasePriceDecisionContext(reviewContext = {}) {
  if (reviewContext.objectType !== 'PurchasePriceReviewContext'
    || !reviewContext.reviewContextId
    || reviewContext.source !== 'SupplierPriceFactRuntime') {
    throw new Error('PURCHASE_PRICE_REVIEW_CONTEXT_REQUIRED')
  }
  return Object.freeze({
    objectType: 'PurchasePriceDecisionContext',
    contextVersion: PURCHASE_PRICE_DECISION_CONTEXT_VERSION,
    reviewContextId: reviewContext.reviewContextId,
    quotationFactId: reviewContext.currentQuotationFact?.priceFactId || '',
    decisionStatus: 'PENDING_MANUAL_CONFIRMATION',
    decisionStatusLabel: '待人工确认',
    caseMarker: 'TEST_CASE',
    auditMode: 'memory_session_only',
    persisted: false,
    manualDecisionRecorded: false,
    automaticPriceDecision: false,
    automaticSupplierSelection: false,
    automaticPriceModification: false,
    automaticPurchaseOrderCreation: false,
    businessStateAdvanced: false,
    businessProgressWriteCount: 0,
  })
}

export function confirmPurchasePriceDecisionContext(context = {}, input = {}, now = () => new Date().toISOString()) {
  if (context.objectType !== 'PurchasePriceDecisionContext'
    || context.decisionStatus !== 'PENDING_MANUAL_CONFIRMATION'
    || context.persisted !== false
    || context.auditMode !== 'memory_session_only') {
    throw new Error('PURCHASE_PRICE_DECISION_CONTEXT_NOT_CONFIRMABLE')
  }
  const reviewOpinion = String(input.reviewOpinion || '').trim()
  const confirmedBy = String(input.confirmedBy || '').trim()
  const confirmationResult = String(input.confirmationResult || '').trim()
  if (!reviewOpinion || !confirmedBy || !['PASS', 'REJECT', 'ADJUST'].includes(confirmationResult)) {
    throw new Error('MANUAL_PRICE_DECISION_FIELDS_REQUIRED')
  }
  const confirmedAt = now()
  return Object.freeze({
    ...context,
    decisionStatus: 'MANUALLY_CONFIRMED_TEST_CASE',
    decisionStatusLabel: '人工确认（测试会话）',
    reviewOpinion,
    confirmedBy,
    confirmedAt,
    confirmationResult,
    auditRecordId: `PPDA-${context.reviewContextId}-${confirmedAt}`,
    auditRecordType: 'TEST_CASE_SESSION_AUDIT',
    manualDecisionRecorded: true,
    persisted: false,
    isBusinessDecision: false,
    businessStateAdvanced: false,
    businessProgressWriteCount: 0,
  })
}
