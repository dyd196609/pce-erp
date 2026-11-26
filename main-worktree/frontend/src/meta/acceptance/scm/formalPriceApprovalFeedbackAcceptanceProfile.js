export const FORMAL_PRICE_APPROVAL_FEEDBACK_ACCEPTANCE_VERSION = 'V1.14.2.8.6.23'

export const FORMAL_PRICE_APPROVAL_FEEDBACK_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_FEEDBACK_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_FEEDBACK_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_FEEDBACK_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['formal-price-approval-feedback']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  commentMeansApprovalResult: false,
  feedbackMeansBusinessChange: false,
  feedbackMeansTaskExecution: false,
  commentInstanceCount: 0,
  feedbackInstanceCount: 0,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalFeedbackAcceptance(profile = FORMAL_PRICE_APPROVAL_FEEDBACK_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.commentMeansApprovalResult === false
    && profile.feedbackMeansBusinessChange === false
    && profile.feedbackMeansTaskExecution === false
    && profile.commentInstanceCount === 0
    && profile.feedbackInstanceCount === 0
    && profile.businessWriteCount === 0
    && profile.databaseState === 'UNCHANGED'
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
