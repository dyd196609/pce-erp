import { supplierCandidateProvider } from '../../../providers/supplierCandidateProvider.js'
import { createSupplierRecommendationRuntimeContextV11428163 } from '../supplierRecommendation/supplierRecommendationRuntimeContextV11428163.js'

export const PRICE_APPROVAL_SUPPLIER_RECOMMENDATION_HANDOFF_VERSION_V11428161 = 'V1.14.2.8.18.16.1'
export const PRICE_APPROVAL_SUPPLIER_RECOMMENDATION_HANDOFF_STORAGE_KEY_V11428161 =
  'pce.scm.price-approval.supplier-recommendation-handoff.v11428161'

const clone = value => JSON.parse(JSON.stringify(value))
const text = value => String(value ?? '').trim()
const freeze = value => Object.freeze(value)
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null
const memoryHandoffs = []

export function createPriceApprovalSupplierRecommendationHandoffV11428161(input = {},
  now = new Date().toISOString()) {
  const supplierCandidates = Array.isArray(input.supplierCandidates) ? input.supplierCandidates : []
  const priceEvidence = Array.isArray(input.priceEvidence) ? input.priceEvidence : []
  const historicalPriceEvidence = Array.isArray(input.historicalPriceEvidence)
    ? input.historicalPriceEvidence : []
  const supplierQualificationFacts = Array.isArray(input.supplierQualificationFacts)
    ? input.supplierQualificationFacts : []
  const priceApprovalNo = text(input.priceApprovalNo || input.priceApprovalId)
  if (!text(input.priceApprovalId) || !text(input.quoteComparisonId) || !text(input.materialCode)
    || !supplierCandidates.length || !priceEvidence.length) {
    throw new Error('PRICE_APPROVAL_RECOMMENDATION_HANDOFF_INCOMPLETE')
  }
  const preparationNo = `SRDP-${text(input.priceApprovalId)}-${text(input.materialCode)}`
  const comparisons = supplierCandidates.map(candidate => {
    const evidence = priceEvidence.find(item => text(item.supplierCode) === text(candidate.supplierCode)) || {}
    return freeze({
      objectType: 'QuoteComparison',
      comparisonNo: text(input.quoteComparisonId),
      inquiryNo: text(input.sourceInquiryNo),
      materialCode: text(input.materialCode),
      materialName: text(input.materialName),
      supplierCode: text(candidate.supplierCode),
      supplierName: text(candidate.supplierName),
      unitPrice: Number(candidate.quotePrice ?? evidence.currentPrice ?? 0),
      totalPrice: Number(candidate.totalPrice ?? candidate.quotePrice ?? evidence.currentPrice ?? 0),
      deliveryDate: text(candidate.deliveryDate),
      comparisonResult: freeze({
        priceRank: Number(candidate.priceRank ?? evidence.priceRank ?? 0),
        deliveryRank: Number(candidate.deliveryRank ?? evidence.deliveryRank ?? 0),
        validityStatus: text(candidate.validityStatus || evidence.validityStatus || 'unknown'),
      }),
    })
  })
  const preparation = freeze({
    objectType: 'SupplierRecommendationDecisionPreparationContext',
    recommendationPreparationNo: preparationNo,
    comparisonPreparationNo: text(input.quoteComparisonId),
    sourceQuoteComparisonId: text(input.quoteComparisonId),
    priceApprovalId: text(input.priceApprovalId),
    priceApprovalNo,
    quoteComparisonId: text(input.quoteComparisonId),
    sourceInquiryNo: text(input.sourceInquiryNo),
    sourceRequestNo: text(input.sourceRequestNo),
    materialCode: text(input.materialCode),
    materialName: text(input.materialName),
    supplierCandidates: freeze(supplierCandidates.map(item => freeze({ ...item }))),
    supplierQualificationFacts: freeze(supplierQualificationFacts.map(item => freeze({ ...item }))),
    priceEvidence: freeze(priceEvidence.map(item => freeze({ ...item }))),
    historicalPriceEvidence: freeze(historicalPriceEvidence.map(item => freeze({ ...item }))),
    priceReferenceRecords: freeze((input.priceReferenceRecords || []).map(item => freeze({ ...item }))),
    comparisons: freeze(comparisons),
    preparationStatus: 'comparison_ready',
    factScope: 'real_price_approval_handoff',
    readOnly: false,
    createdAt: now,
    purchaseOrderCreated: false,
    financeCreated: false,
    wmsCreated: false,
    mesCreated: false,
    productionDataWritten: false,
  })
  const runtimeContext = createSupplierRecommendationRuntimeContextV11428163({ preparation }, now)
  return freeze({
    objectType: 'PriceApprovalSupplierRecommendationHandoff',
    handoffId: `PA-SR-HANDOFF-${text(input.priceApprovalId)}-${text(input.materialCode)}`,
    sourceObjectType: 'PriceApproval',
    sourceObjectId: text(input.priceApprovalId),
    targetObjectType: 'SupplierRecommendationRuntimeContext',
    priceApprovalId: text(input.priceApprovalId),
    priceApprovalNo,
    quoteComparisonId: text(input.quoteComparisonId),
    materialCode: text(input.materialCode),
    supplierCandidates: preparation.supplierCandidates,
    priceEvidence: preparation.priceEvidence,
    historicalPriceEvidence: preparation.historicalPriceEvidence,
    runtimeContext,
    preparation,
    handoffStatus: 'ready',
    businessWriteCount: 1,
    productionDataWritten: false,
    purchaseOrderCreated: false,
  })
}

export function createPriceApprovalSupplierRecommendationHandoffStoreV11428161({
  storage = browserStorage(), storageKey = PRICE_APPROVAL_SUPPLIER_RECOMMENDATION_HANDOFF_STORAGE_KEY_V11428161,
} = {}) {
  const read = () => {
    if (!storage) return clone(memoryHandoffs)
    try {
      const value = JSON.parse(storage.getItem(storageKey) || '[]')
      return Array.isArray(value) ? value : []
    } catch { return [] }
  }
  const write = values => {
    memoryHandoffs.splice(0, memoryHandoffs.length, ...clone(values))
    storage?.setItem(storageKey, JSON.stringify(values))
    return clone(values)
  }
  return freeze({
    listHandoffs: read,
    listRuntimeContexts: () => read().map(item => item.runtimeContext).filter(Boolean),
    listPreparations: () => read().map(item => item.preparation),
    saveHandoff(handoff) {
      const values = read()
      const index = values.findIndex(item => item.handoffId === handoff.handoffId)
      if (index < 0) values.push(clone(handoff)); else values.splice(index, 1, clone(handoff))
      return write(values).find(item => item.handoffId === handoff.handoffId)
    },
    clear: () => write([]),
  })
}

export const priceApprovalSupplierRecommendationHandoffStoreV11428161 =
  createPriceApprovalSupplierRecommendationHandoffStoreV11428161()

export function executePriceApprovalSupplierRecommendationHandoffV11428161(input = {},
  store = priceApprovalSupplierRecommendationHandoffStoreV11428161,
  qualificationProvider = supplierCandidateProvider) {
  try {
    const masterOptions = qualificationProvider?.load?.({ query: '' })?.options || []
    const supplierQualificationFacts = (input.supplierQualificationFacts || input.supplierCandidates || [])
      .map(candidate => {
        if (candidate.qualificationStatus) return candidate
        const master = masterOptions.find(item => text(item.supplierCode) === text(candidate.supplierCode))
        return {
          supplierCode: text(candidate.supplierCode),
          supplierName: text(candidate.supplierName || master?.supplierName),
          qualificationStatus: master && !['inactive', 'disabled', 'restricted']
            .includes(text(master.supplierStatus).toLowerCase()) ? 'qualified' : 'unverified',
          supplierStatus: text(master?.supplierStatus || 'unverified'),
          supplierCategory: text(master?.supplierCategory || 'unclassified'),
          evidenceSource: text(master?.source || qualificationProvider?.source || 'Supplier Master'),
        }
      })
    const handoff = createPriceApprovalSupplierRecommendationHandoffV11428161({
      ...input, supplierQualificationFacts,
    })
    return freeze({ result: 'PASS', handoff: store.saveHandoff(handoff),
      navigationTarget: '/scm/supplier-recommendations', purchaseOrderCreated: false,
      productionDataWritten: false })
  } catch (error) {
    return freeze({ result: 'FAIL', error: error.message, purchaseOrderCreated: false,
      productionDataWritten: false })
  }
}
