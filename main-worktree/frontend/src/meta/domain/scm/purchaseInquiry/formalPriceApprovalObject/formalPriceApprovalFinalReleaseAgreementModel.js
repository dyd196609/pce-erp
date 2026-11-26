export const FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_MODEL_VERSION = 'V1.14.2.8.6.13'

export const FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_STATES = Object.freeze([
  'not_requested',
  'pending_review',
  'agreed_design_only',
  'rejected',
])

export const FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT = Object.freeze({
  agreementCode: 'SCM_FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT',
  version: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_MODEL_VERSION,
  agreementKind: 'HUMAN_RESPONSIBILITY_PROTOCOL_ONLY',
  fields: Object.freeze([
    'agreementNo',
    'inquiryNo',
    'sandboxNo',
    'confirmationNo',
    'requesterId',
    'reviewerId',
    'executorRoleId',
    'agreementStatus',
    'responsibilityStatement',
    'reviewedAt',
  ]),
  lifecycle: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_STATES,
  requesterReviewerSeparationRequired: true,
  reviewerExecutorSeparationRequired: true,
  executionPermissionGranted: false,
  agreementInstanceCount: 0,
  persistenceMode: 'none',
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalFinalReleaseAgreement(model = FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT) {
  const valid = model.agreementCode === 'SCM_FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT'
    && model.agreementKind === 'HUMAN_RESPONSIBILITY_PROTOCOL_ONLY'
    && model.lifecycle.join(',') === 'not_requested,pending_review,agreed_design_only,rejected'
    && model.requesterReviewerSeparationRequired === true
    && model.reviewerExecutorSeparationRequired === true
    && model.executionPermissionGranted === false
    && model.agreementInstanceCount === 0
    && model.persistenceMode === 'none'
    && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
