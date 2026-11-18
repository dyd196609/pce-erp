export const SUPPLIER_RECOMMENDATION_DOMAIN_VERSION_V1142811 = 'V1.14.2.8.18.11'

const text = value => String(value ?? '').trim()
const frozen = value => Object.freeze(value)
const freezeList = values => frozen(values.map(item => frozen({ ...item })))

function supplierMasterRecords(provider) {
  const facts = provider?.load?.() || { options: [] }
  return Array.isArray(facts.options) ? facts.options : []
}

export function createSupplierRecommendationDecisionContext(preparation = {}, supplierProvider,
  now = new Date().toISOString()) {
  if (preparation.objectType !== 'SupplierRecommendationDecisionPreparationContext'
    || preparation.preparationStatus !== 'comparison_ready'
    || !text(preparation.recommendationPreparationNo)
    || !Array.isArray(preparation.comparisons) || !preparation.comparisons.length) {
    throw new Error('SUPPLIER_RECOMMENDATION_PREPARATION_NOT_READY')
  }
  const masters = supplierMasterRecords(supplierProvider)
  const candidates = preparation.comparisons.map(comparison => {
    const qualificationFact = (preparation.supplierQualificationFacts || [])
      .find(item => text(item.supplierCode) === text(comparison.supplierCode))
    const master = masters.find(item => text(item.supplierCode) === text(comparison.supplierCode))
    const supplierStatus = text(qualificationFact?.supplierStatus || master?.supplierStatus || 'unverified')
    const qualificationStatus = text(qualificationFact?.qualificationStatus
      || (master ? (['active', 'enabled'].includes(supplierStatus) ? 'qualified' : 'restricted') : 'unverified'))
    return frozen({
      materialCode: text(comparison.materialCode),
      materialName: text(comparison.materialName),
      supplierCode: text(comparison.supplierCode),
      supplierName: text(comparison.supplierName),
      supplierStatus,
      supplierCategory: text(qualificationFact?.supplierCategory || master?.supplierCategory || 'unclassified'),
      qualificationStatus,
      source: qualificationFact?.evidenceSource || master?.source || 'Supplier Master',
    })
  })
  const evidence = preparation.comparisons.map((comparison, index) => frozen({
    objectType: 'SupplierRecommendationEvidence',
    evidenceNo: `SRE-${preparation.recommendationPreparationNo}-${index + 1}`,
    sourceObjectType: 'QuoteComparison',
    sourceObjectId: text(comparison.comparisonNo),
    materialCode: text(comparison.materialCode),
    materialName: text(comparison.materialName),
    supplierCode: text(comparison.supplierCode),
    supplierName: text(comparison.supplierName),
    quoteBasis: frozen({ unitPrice: Number(comparison.unitPrice || 0), totalPrice: Number(comparison.totalPrice || 0) }),
    priceEvidence: frozen({ unitPrice: Number(comparison.unitPrice || 0),
      totalPrice: Number(comparison.totalPrice || 0), rank: Number(comparison.comparisonResult?.priceRank || 0) }),
    priceRank: Number(comparison.comparisonResult?.priceRank || 0),
    deliveryBasis: frozen({ deliveryDate: text(comparison.deliveryDate), rank: Number(comparison.comparisonResult?.deliveryRank || 0) }),
    deliveryEvidence: frozen({ deliveryDate: text(comparison.deliveryDate),
      rank: Number(comparison.comparisonResult?.deliveryRank || 0) }),
    validityStatus: text(comparison.comparisonResult?.validityStatus),
    qualificationStatus: candidates[index].qualificationStatus,
    qualificationEvidence: frozen({ supplierStatus: candidates[index].supplierStatus,
      supplierCategory: candidates[index].supplierCategory,
      qualificationStatus: candidates[index].qualificationStatus, source: candidates[index].source }),
    comparisonEvidence: frozen({ comparisonNo: text(comparison.comparisonNo),
      priceRank: Number(comparison.comparisonResult?.priceRank || 0),
      deliveryRank: Number(comparison.comparisonResult?.deliveryRank || 0),
      validityStatus: text(comparison.comparisonResult?.validityStatus) }),
    historicalPriceEvidence: null,
  }))
  if (candidates.some(item => !item.materialCode || !item.supplierCode)
    || evidence.some(item => !item.sourceObjectId || item.priceRank <= 0)) {
    throw new Error('SUPPLIER_RECOMMENDATION_EVIDENCE_INCOMPLETE')
  }
  return frozen({
    objectType: 'SupplierRecommendationDecisionContext',
    decisionContextNo: `SRDC-${text(preparation.recommendationPreparationNo)}`,
    sourceQuoteComparisonId: text(preparation.comparisonPreparationNo),
    sourceObjectType: preparation.objectType,
    sourceObjectId: text(preparation.recommendationPreparationNo),
    comparisonPreparationNo: text(preparation.comparisonPreparationNo),
    sourceInquiryNo: text(preparation.sourceInquiryNo),
    sourceRequestNo: text(preparation.sourceRequestNo),
    priceApprovalId: text(preparation.priceApprovalId),
    priceApprovalNo: text(preparation.priceApprovalNo || preparation.priceApprovalId),
    quoteComparisonId: text(preparation.quoteComparisonId || preparation.sourceQuoteComparisonId),
    quoteComparisonResult: frozen({ comparisonPreparationNo: text(preparation.comparisonPreparationNo),
      comparisons: freezeList(preparation.comparisons) }),
    materialCode: [...new Set(candidates.map(item => item.materialCode))].length === 1 ? candidates[0].materialCode : '',
    materialName: [...new Set(candidates.map(item => item.materialCode))].length === 1 ? candidates[0].materialName : '',
    supplierCandidates: freezeList(candidates),
    supplier: freezeList([...new Map(candidates.map(item => [item.supplierCode,
      { supplierCode: item.supplierCode, supplierName: item.supplierName }])).values()]),
    material: freezeList([...new Map(candidates.map(item => [item.materialCode,
      { materialCode: item.materialCode, materialName: item.materialName }])).values()]),
    evidence: frozen(evidence),
    priceRanking: frozen(evidence.map(item => frozen({ materialCode: item.materialCode,
      supplierCode: item.supplierCode, priceRank: item.priceRank }))),
    priceEvidence: frozen(evidence.map(item => item.priceEvidence)),
    deliveryEvidence: frozen(evidence.map(item => item.deliveryEvidence)),
    qualificationEvidence: frozen(evidence.map(item => item.qualificationEvidence)),
    recommendationReason: '',
    recommendationStatus: 'created',
    manualDecisionStatus: 'created',
    decisionMode: 'manual_only',
    createdAt: now,
    updatedAt: now,
    purchaseOrderCreated: false,
    supplierContacted: false,
    financeCreated: false,
    wmsCreated: false,
    mesCreated: false,
  })
}

export function createRecommendationApprovalContext(context = {}, now = new Date().toISOString()) {
  if (context.objectType !== 'SupplierRecommendationDecisionContext'
    || context.recommendationStatus !== 'decision_prepared') {
    throw new Error('RECOMMENDATION_DECISION_NOT_PREPARED')
  }
  const materials = [...new Map(context.supplierCandidates.map(item => [item.materialCode,
    frozen({ materialCode: item.materialCode, materialName: item.materialName })])).values()]
  return frozen({
    objectType: 'RecommendationApprovalContext',
    approvalContextNo: `RAC-${context.sourceInquiryNo}`,
    decisionContextNo: context.decisionContextNo,
    reviewType: 'manual_supplier_recommendation_confirmation',
    requiredMaterials: frozen(materials),
    manualConfirmationStatus: 'pending',
    reviewStatus: 'pending',
    reviewer: '',
    reviewComment: '',
    selectedRecommendations: frozen([]),
    recommendationReason: '',
    createdAt: now,
  })
}

export function createSupplierRecommendationDecision(context = {}, approval = {}, input = {},
  now = new Date().toISOString()) {
  if (context.recommendationStatus !== 'manual_review'
    || approval.objectType !== 'RecommendationApprovalContext'
    || approval.manualConfirmationStatus !== 'pending') {
    throw new Error('SUPPLIER_RECOMMENDATION_MANUAL_REVIEW_NOT_READY')
  }
  const selections = Array.isArray(input.selections) ? input.selections : []
  const reason = text(input.reason)
  const confirmedBy = text(input.confirmedBy)
  const requiredMaterials = approval.requiredMaterials.map(item => item.materialCode)
  const complete = requiredMaterials.every(materialCode => selections.some(item => item.materialCode === materialCode))
  const selectionsValid = selections.every(selection => context.supplierCandidates.some(candidate =>
    candidate.materialCode === selection.materialCode && candidate.supplierCode === selection.supplierCode))
  if (!complete || !selectionsValid || !reason || !confirmedBy) {
    throw new Error('MANUAL_RECOMMENDATION_CONFIRMATION_INCOMPLETE')
  }
  const selectedRecommendations = freezeList(selections.map(selection => {
    const candidate = context.supplierCandidates.find(item => item.materialCode === selection.materialCode
      && item.supplierCode === selection.supplierCode)
    const evidenceReferences = context.evidence.filter(item => item.materialCode === selection.materialCode
      && item.supplierCode === selection.supplierCode).map(item => item.evidenceNo)
    return { materialCode: candidate.materialCode, materialName: candidate.materialName,
      supplierCode: candidate.supplierCode, supplierName: candidate.supplierName,
      supplierStatus: candidate.supplierStatus, qualificationStatus: candidate.qualificationStatus,
      evidenceReferences: frozen(evidenceReferences), recommendationReason: reason }
  }))
  return frozen({
    objectType: 'SupplierRecommendationDecision',
    decisionNo: `SRD-${context.sourceObjectId}`,
    decisionId: `SRD-${context.sourceObjectId}`,
    decisionContextNo: context.decisionContextNo,
    sourceObjectType: context.sourceObjectType,
    sourceObjectId: context.sourceObjectId,
    sourceInquiryNo: context.sourceInquiryNo,
    sourceRequestNo: context.sourceRequestNo,
    priceApprovalId: context.priceApprovalId,
    priceApprovalNo: context.priceApprovalNo,
    quoteComparisonId: context.quoteComparisonId,
    sourceQuoteComparisonId: context.sourceQuoteComparisonId,
    selectedRecommendations,
    supplier: frozen(selectedRecommendations.map(item => frozen({ supplierCode: item.supplierCode,
      supplierName: item.supplierName }))),
    material: frozen(selectedRecommendations.map(item => frozen({ materialCode: item.materialCode,
      materialName: item.materialName }))),
    comparisonEvidence: context.evidence,
    recommendationEvidence: selectedRecommendations,
    recommendationReason: reason,
    decisionReason: reason,
    manualConfirmationStatus: 'confirmed',
    confirmedBy,
    confirmedAt: now,
    manualReviewer: confirmedBy,
    manualReviewedAt: now,
    manualConfirmedAt: now,
    decisionStatus: 'confirmed',
    recommendationStatus: 'confirmed',
    decisionMode: 'manual_only',
    purchaseOrderCreated: false,
    supplierContacted: false,
    financeCreated: false,
    wmsCreated: false,
    mesCreated: false,
  })
}

export function validateSupplierRecommendationDomainV1142811(context = {}, decision = null) {
  const contextValid = context.objectType === 'SupplierRecommendationDecisionContext'
    && context.decisionMode === 'manual_only' && context.supplierCandidates?.length > 0
    && context.evidence?.length > 0 && context.purchaseOrderCreated === false
  const decisionValid = !decision || (decision.objectType === 'SupplierRecommendationDecision'
    && decision.decisionMode === 'manual_only' && decision.manualConfirmationStatus === 'confirmed'
    && decision.selectedRecommendations?.length > 0 && decision.purchaseOrderCreated === false)
  return frozen({ valid: contextValid && decisionValid, result: contextValid && decisionValid ? 'PASS' : 'FAIL' })
}
