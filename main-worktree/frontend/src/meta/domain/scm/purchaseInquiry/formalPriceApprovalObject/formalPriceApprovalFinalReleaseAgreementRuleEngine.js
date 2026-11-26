import { evaluateFormalPriceApprovalFinalReleaseAgreementChecklist } from './formalPriceApprovalFinalReleaseAgreementChecklist.js'

export const FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_RULE_VERSION = 'V1.14.2.8.6.13'

export function evaluateFormalPriceApprovalFinalReleaseAgreement(input = {}) {
  if (input.agreementRequested !== true) {
    return Object.freeze({ result: 'PASS', decision: 'not_requested', evaluatedStatus: 'not_requested', agreementInstanceCreated: false, executionPermissionGranted: false, commandExecuted: false, formalPriceApprovalObjectCreated: false, approvalWorkflowStarted: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const requesterId = typeof input.requesterId === 'string' ? input.requesterId.trim() : ''
  const reviewerId = typeof input.reviewerId === 'string' ? input.reviewerId.trim() : ''
  const executorRoleId = typeof input.executorRoleId === 'string' ? input.executorRoleId.trim() : ''
  const requesterReviewerSeparated = requesterId.length > 0 && reviewerId.length > 0 && requesterId !== reviewerId
  const reviewerExecutorSeparated = reviewerId.length > 0 && executorRoleId.length > 0 && reviewerId !== executorRoleId
  const checklist = evaluateFormalPriceApprovalFinalReleaseAgreementChecklist({
    ...input,
    requesterReviewerSeparated,
    reviewerExecutorSeparated,
  })
  const identityConflict = (requesterId.length > 0 && reviewerId.length > 0 && requesterId === reviewerId)
    || (reviewerId.length > 0 && executorRoleId.length > 0 && reviewerId === executorRoleId)
  const automaticReview = input.reviewMode !== 'human'
  const evaluatedStatus = identityConflict || automaticReview ? 'rejected' : (checklist.complete ? 'agreed_design_only' : 'pending_review')
  return Object.freeze({
    result: evaluatedStatus === 'agreed_design_only' ? 'PASS' : 'FAIL',
    decision: evaluatedStatus,
    evaluatedStatus,
    checklist,
    requesterReviewerSeparated,
    reviewerExecutorSeparated,
    agreementInstanceCreated: false,
    executionPermissionGranted: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
