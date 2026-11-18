export const FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ACCEPTANCE_VERSION = 'V1.14.2.8.6.11'

export const FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_FINAL_RELEASE_READY',
  route: '/scm/purchase-inquiry',
  assessmentCode: 'SCM_FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT',
  requiredRegions: Object.freeze(['formal-price-approval-final-release-assessment']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  finalReleaseIsExecution: false,
  readyMeansCreated: false,
  gateIsCommandExecutor: false,
  executionPermissionGranted: false,
  commandExecuted: false,
  formalPriceApprovalObjectCreated: false,
  approvalWorkflowStarted: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalFinalReleaseAcceptance(profile = FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.finalReleaseIsExecution === false
    && profile.readyMeansCreated === false
    && profile.gateIsCommandExecutor === false
    && profile.executionPermissionGranted === false
    && profile.commandExecuted === false
    && profile.formalPriceApprovalObjectCreated === false
    && profile.approvalWorkflowStarted === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
