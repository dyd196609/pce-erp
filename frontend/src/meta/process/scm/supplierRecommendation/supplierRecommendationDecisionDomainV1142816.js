export const SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_VERSION_V1142816 = 'V1.14.2.8.18.16'

const text = value => String(value ?? '').trim()
const freeze = value => Object.freeze(value)
const freezeList = values => freeze(values.map(item => freeze({ ...item })))

const qualificationFor = (preparation, supplierCode, supplierFacts = []) =>
  (preparation.supplierQualificationFacts || []).find(item => text(item.supplierCode) === text(supplierCode))
  || supplierFacts.find(item => text(item.supplierCode) === text(supplierCode))
  || {}

export function createSupplierRecommendationEvidenceV1142816({ comparison = {}, priceReference = null,
  qualification = {} } = {}) {
  return freeze({
    objectType: 'SupplierRecommendationEvidence',
    materialCode: text(comparison.materialCode),
    supplierCode: text(comparison.supplierCode),
    priceEvidence: freeze({
      currentPrice: Number(comparison.unitPrice || 0),
      totalPrice: Number(comparison.totalPrice || 0),
      priceRank: Number(comparison.comparisonResult?.priceRank || 0),
    }),
    historicalPriceEvidence: priceReference?.priceReferenceContext || null,
    qualificationEvidence: freeze({
      supplierStatus: text(qualification.supplierStatus || 'unverified'),
      supplierCategory: text(qualification.supplierCategory || 'unclassified'),
      qualificationStatus: text(qualification.qualificationStatus || 'unverified'),
      evidenceSource: text(qualification.evidenceSource || qualification.source || 'SupplierQualificationContext'),
    }),
    comparisonEvidence: freeze({
      comparisonNo: text(comparison.comparisonNo),
      deliveryDate: text(comparison.deliveryDate),
      priceRank: Number(comparison.comparisonResult?.priceRank || 0),
      deliveryRank: Number(comparison.comparisonResult?.deliveryRank || 0),
      validityStatus: text(comparison.comparisonResult?.validityStatus),
    }),
  })
}

export function createSupplierRecommendationDecisionContextV1142816({ preparation = {}, runtimeContext = null,
  priceReferenceRecords = [], supplierQualificationFacts = [] } = {}) {
  if (preparation.objectType !== 'SupplierRecommendationDecisionPreparationContext'
    || preparation.preparationStatus !== 'comparison_ready'
    || !Array.isArray(preparation.comparisons) || !preparation.comparisons.length) {
    throw new Error('SUPPLIER_RECOMMENDATION_DECISION_INPUT_NOT_READY')
  }
  const comparisons = preparation.comparisons
  const materials = [...new Map(comparisons.map(item => [text(item.materialCode), {
    materialCode: text(item.materialCode), materialName: text(item.materialName),
  }])).values()]
  const supplierCandidates = runtimeContext?.supplierCandidates || comparisons.map(comparison => {
    const qualification = qualificationFor(preparation, comparison.supplierCode, supplierQualificationFacts)
    return freeze({
      materialCode: text(comparison.materialCode), materialName: text(comparison.materialName),
      supplierCode: text(comparison.supplierCode), supplierName: text(comparison.supplierName),
      supplierStatus: text(qualification.supplierStatus || 'unverified'),
      supplierCategory: text(qualification.supplierCategory || 'unclassified'),
      qualificationStatus: text(qualification.qualificationStatus || 'unverified'),
    })
  })
  const evidence = comparisons.map(comparison => createSupplierRecommendationEvidenceV1142816({
    comparison,
    priceReference: priceReferenceRecords.find(item => text(item.materialCode) === text(comparison.materialCode)
      && text(item.supplierCode) === text(comparison.supplierCode)),
    qualification: qualificationFor(preparation, comparison.supplierCode, supplierQualificationFacts),
  }))
  return freeze({
    ...(runtimeContext || {}),
    objectType: 'SupplierRecommendationDecisionContext',
    sourceQuoteComparisonId: text(preparation.sourceQuoteComparisonId || preparation.comparisonPreparationNo),
    quoteComparisonResult: freeze({
      comparisonPreparationNo: text(preparation.comparisonPreparationNo),
      comparisonCount: comparisons.length,
      comparisons: freezeList(comparisons),
    }),
    materialCode: materials.length === 1 ? materials[0].materialCode : '',
    materialName: materials.length === 1 ? materials[0].materialName : '',
    materials: freezeList(materials),
    supplierCandidates: freezeList(supplierCandidates),
    priceEvidence: freeze(evidence.map(item => item.priceEvidence)),
    deliveryEvidence: freeze(evidence.map(item => item.comparisonEvidence)),
    qualificationEvidence: freeze(evidence.map(item => item.qualificationEvidence)),
    recommendationEvidence: freeze(evidence),
    manualDecisionStatus: runtimeContext?.manualDecisionStatus
      || runtimeContext?.recommendationStatus || 'created',
    readOnlyEvidence: true,
    automaticLowestPriceSelection: false,
    aiRecommendation: false,
    automaticScoring: false,
    purchaseOrderCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export function createRecommendationConfirmationContextV1142816(value = {}) {
  const reviewStatus = text(value.reviewStatus || value.manualConfirmationStatus || 'pending')
  return freeze({
    objectType: 'RecommendationConfirmationContext',
    reviewStatus,
    reviewer: text(value.reviewer || value.confirmedBy),
    reviewComment: text(value.reviewComment || value.recommendationReason),
    confirmedAt: value.confirmedAt || null,
  })
}

export function createSupplierRecommendationDecisionV1142816(context = {}, confirmation = {}, input = {},
  now = new Date().toISOString()) {
  if (context.objectType !== 'SupplierRecommendationDecisionContext'
    || context.manualDecisionStatus !== 'manual_review') {
    throw new Error('SUPPLIER_RECOMMENDATION_MANUAL_REVIEW_REQUIRED')
  }
  const supplierCode = text(input.supplierCode)
  const materialCode = text(input.materialCode || context.materialCode)
  const decisionReason = text(input.decisionReason)
  const manualReviewer = text(input.manualReviewer || confirmation.reviewer)
  const candidate = context.supplierCandidates.find(item => item.materialCode === materialCode
    && item.supplierCode === supplierCode)
  if (!candidate || !decisionReason || !manualReviewer) {
    throw new Error('MANUAL_RECOMMENDATION_CONFIRMATION_INCOMPLETE')
  }
  return freeze({
    objectType: 'SupplierRecommendationDecision',
    decisionId: text(input.decisionId || `SRD-${context.sourceQuoteComparisonId}-${materialCode}`),
    supplierCode: candidate.supplierCode,
    supplierName: candidate.supplierName,
    materialCode,
    decisionStatus: 'confirmed',
    decisionReason,
    manualReviewer,
    manualReviewedAt: now,
    sourceQuoteComparisonId: context.sourceQuoteComparisonId,
    recommendationEvidence: freeze(context.recommendationEvidence.filter(item =>
      item.materialCode === materialCode && item.supplierCode === supplierCode)),
    automaticDecision: false,
    purchaseOrderCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
