export const FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_ACCEPTANCE_VERSION = 'V1.14.2.8.6.17'

export const FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_READY',
  route: '/scm/purchase-inquiry',
  stateMachineCode: 'SCM_FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE',
  requiredRegions: Object.freeze(['formal-price-approval-post-creation-lifecycle']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  createdIsPendingApproval: false,
  approvedMeansAutoExecution: false,
  lifecycleIsWorkflow: false,
  transitionCount: 4,
  enabledTransitionCount: 0,
  lifecycleExecuted: false,
  statePersisted: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalPostCreationLifecycleAcceptance(profile = FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.createdIsPendingApproval === false
    && profile.approvedMeansAutoExecution === false
    && profile.lifecycleIsWorkflow === false
    && profile.transitionCount === 4
    && profile.enabledTransitionCount === 0
    && profile.lifecycleExecuted === false
    && profile.statePersisted === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
