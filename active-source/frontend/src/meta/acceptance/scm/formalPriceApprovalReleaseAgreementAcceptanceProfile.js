export const FORMAL_PRICE_APPROVAL_RELEASE_AGREEMENT_ACCEPTANCE_VERSION = 'V1.14.2.8.6.13'

export const FORMAL_PRICE_APPROVAL_RELEASE_AGREEMENT_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_RELEASE_AGREEMENT_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_RELEASE_AGREEMENT_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_RELEASE_AGREEMENT_READY',
  route: '/scm/purchase-inquiry',
  agreementCode: 'SCM_FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT',
  requiredRegions: Object.freeze(['formal-price-approval-final-release-agreement']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  requesterReviewerSeparationRequired: true,
  reviewerExecutorSeparationRequired: true,
  agreementIsExecution: false,
  executionPermissionGranted: false,
  commandExecuted: false,
  formalPriceApprovalObjectCreated: false,
  approvalWorkflowStarted: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalReleaseAgreementAcceptance(profile = FORMAL_PRICE_APPROVAL_RELEASE_AGREEMENT_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.requesterReviewerSeparationRequired === true
    && profile.reviewerExecutorSeparationRequired === true
    && profile.agreementIsExecution === false
    && profile.executionPermissionGranted === false
    && profile.commandExecuted === false
    && profile.formalPriceApprovalObjectCreated === false
    && profile.approvalWorkflowStarted === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
