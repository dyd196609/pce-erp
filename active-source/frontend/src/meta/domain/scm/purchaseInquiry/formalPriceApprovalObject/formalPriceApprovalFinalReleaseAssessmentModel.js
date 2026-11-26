export const FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT_MODEL_VERSION = 'V1.14.2.8.6.11'

export const FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT_STATES = Object.freeze([
  'not_assessed',
  'checking',
  'ready',
  'blocked',
  'manual_review',
])

export const FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT = Object.freeze({
  assessmentCode: 'SCM_FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT',
  version: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT_MODEL_VERSION,
  assessmentKind: 'FINAL_SAFETY_REVIEW_ONLY',
  fields: Object.freeze([
    'assessmentNo',
    'inquiryNo',
    'commandNo',
    'authorizationNo',
    'auditCode',
    'assessmentStatus',
    'findings',
    'blockedReasons',
    'manualReviewReasons',
  ]),
  lifecycle: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT_STATES,
  releaseIsExecution: false,
  readyMeansCreated: false,
  assessmentInstanceCount: 0,
  persistenceMode: 'none',
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalFinalReleaseAssessment(model = FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT) {
  const valid = model.assessmentCode === 'SCM_FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT'
    && model.assessmentKind === 'FINAL_SAFETY_REVIEW_ONLY'
    && model.lifecycle.join(',') === 'not_assessed,checking,ready,blocked,manual_review'
    && model.releaseIsExecution === false
    && model.readyMeansCreated === false
    && model.assessmentInstanceCount === 0
    && model.persistenceMode === 'none'
    && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
