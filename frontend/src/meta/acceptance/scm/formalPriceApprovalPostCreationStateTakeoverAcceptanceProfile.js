export const FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_ACCEPTANCE_VERSION = 'V1.14.2.8.6.16'

export const FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_ISOLATION_READY',
  route: '/scm/purchase-inquiry',
  takeoverCode: 'SCM_FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER',
  requiredRegions: Object.freeze(['formal-price-approval-post-creation-state-takeover']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  createdMeansAutoPendingApproval: false,
  takeoverIsStateMutation: false,
  workflowOwnershipMeansWorkflowStart: false,
  stateChanged: false,
  formalPriceApprovalObjectCreatedNow: false,
  approvalWorkflowStarted: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalPostCreationStateTakeoverAcceptance(profile = FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.createdMeansAutoPendingApproval === false
    && profile.takeoverIsStateMutation === false
    && profile.workflowOwnershipMeansWorkflowStart === false
    && profile.stateChanged === false
    && profile.formalPriceApprovalObjectCreatedNow === false
    && profile.approvalWorkflowStarted === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
