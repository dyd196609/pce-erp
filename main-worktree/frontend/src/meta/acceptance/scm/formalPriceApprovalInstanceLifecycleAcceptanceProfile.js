export const FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE_ACCEPTANCE_VERSION = 'V1.14.2.8.6.20'

export const FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['formal-price-approval-instance-task-lifecycle']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  instanceDefinitionMeansCreated: false,
  taskDefinitionMeansCreated: false,
  workflowRunningMeansApprovalResult: false,
  instanceCount: 0,
  taskCount: 0,
  workflowStarted: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalInstanceLifecycleAcceptance(profile = FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.instanceDefinitionMeansCreated === false
    && profile.taskDefinitionMeansCreated === false
    && profile.workflowRunningMeansApprovalResult === false
    && profile.instanceCount === 0
    && profile.taskCount === 0
    && profile.workflowStarted === false
    && profile.businessWriteCount === 0
    && profile.databaseState === 'UNCHANGED'
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
