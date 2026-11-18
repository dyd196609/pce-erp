export const PRICE_APPROVAL_CREATION_RULE_ENGINE_VERSION = 'V1.14.2.8.6.4'

export const PRICE_APPROVAL_CREATION_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'PRICE-CREATION-FREEZE-001', name: '准入评估检查' }),
  Object.freeze({ ruleCode: 'PRICE-CREATION-FREEZE-002', name: '核价准备检查' }),
  Object.freeze({ ruleCode: 'PRICE-CREATION-FREEZE-003', name: '报价证据检查' }),
  Object.freeze({ ruleCode: 'PRICE-CREATION-FREEZE-004', name: '特殊采购评估' }),
])

const present = (value) => value !== undefined && value !== null && String(value).trim() !== ''

export function evaluatePriceApprovalCreationAssessment(input = {}) {
  const entryAssessment = input.entryAssessment || {}
  const preparation = input.preparation || {}
  const quotationEvidence = input.quotationEvidence || {}
  const hasFacts = present(entryAssessment.assessmentStatus)
    || present(preparation.reviewStatus)
    || present(quotationEvidence.status)
  if (!hasFacts) {
    return Object.freeze({
      result: 'NOT_ASSESSED', creationAssessmentStatus: 'not_assessed', rules: Object.freeze([]),
      manualReviewRequired: false, blockedReasons: Object.freeze([]), readyForFormalPriceApprovalCreation: false,
      decisionOnly: true, formalPriceApprovalObjectCreated: false, businessWriteCount: 0, productionDataWritten: false,
    })
  }

  const entryBlocked = ['blocked', 'not_eligible'].includes(entryAssessment.assessmentStatus)
  const entryManual = entryAssessment.assessmentStatus === 'manual_review'
  const entryReady = entryAssessment.assessmentStatus === 'eligible'
  const preparationBlocked = preparation.reviewStatus === 'blocked' || (preparation.blockedReasons || []).length > 0
  const preparationManual = preparation.reviewStatus === 'pending_review'
  const preparationReady = preparation.reviewStatus === 'prepared'
  const quotationCount = Number(quotationEvidence.quotationCount || 0)
  const evidenceBlocked = quotationEvidence.status === 'blocked' || quotationCount < 1
  const evidenceReady = ['complete', 'verified'].includes(quotationEvidence.status) && quotationCount > 0
  const specialManual = input.specialProcurement === true
  const blocked = entryBlocked || preparationBlocked || evidenceBlocked || (!entryReady && !entryManual) || (!preparationReady && !preparationManual) || !evidenceReady
  const manualReview = !blocked && (entryManual || preparationManual || specialManual)
  const creationAssessmentStatus = blocked ? 'blocked' : manualReview ? 'manual_review' : 'ready'
  const blockedReasons = Object.freeze([
    ...(entryBlocked || (!entryReady && !entryManual) ? ['准入评估未通过'] : []),
    ...(preparationBlocked || (!preparationReady && !preparationManual) ? ['核价准备未通过'] : []),
    ...(evidenceBlocked || !evidenceReady ? ['报价证据未通过'] : []),
    ...(preparation.blockedReasons || []),
  ])
  const rules = Object.freeze([
    Object.freeze({ ruleCode: 'PRICE-CREATION-FREEZE-001', result: entryBlocked ? 'FAIL' : entryManual ? 'MANUAL_REVIEW' : entryReady ? 'PASS' : 'FAIL' }),
    Object.freeze({ ruleCode: 'PRICE-CREATION-FREEZE-002', result: preparationBlocked ? 'FAIL' : preparationManual ? 'MANUAL_REVIEW' : preparationReady ? 'PASS' : 'FAIL' }),
    Object.freeze({ ruleCode: 'PRICE-CREATION-FREEZE-003', result: evidenceReady ? 'PASS' : 'FAIL' }),
    Object.freeze({ ruleCode: 'PRICE-CREATION-FREEZE-004', result: specialManual ? 'MANUAL_REVIEW' : 'PASS' }),
  ])
  return Object.freeze({
    result: creationAssessmentStatus.toUpperCase(),
    creationAssessmentStatus,
    rules,
    manualReviewRequired: creationAssessmentStatus === 'manual_review',
    blockedReasons,
    readyForFormalPriceApprovalCreation: creationAssessmentStatus === 'ready',
    decisionOnly: true,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    approvalSubmitted: false,
    priceApproved: false,
    purchaseOrderCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
