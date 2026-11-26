export const FORMAL_PRICE_APPROVAL_NAVIGATION_ACCEPTANCE_VERSION = 'V1.14.2.8.7.2'

export const FORMAL_PRICE_APPROVAL_NAVIGATION_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_NAVIGATION_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_NAVIGATION_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_NAVIGATION_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['formal-price-approval-business-navigation']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  navigationStepCount: 5, roleViewCount: 3,
  navigationMeansExecution: false, userPathMeansWorkflowRuntime: false, nextStepMeansAutoAction: false,
  routeActionEnabled: false, workflowRuntimeConnected: false, autoActionEnabled: false,
  approvalObjectCount: 0, approvalTaskCount: 0, businessWriteCount: 0,
  databaseState: 'UNCHANGED', productionDataWritten: false,
})

export function validateFormalPriceApprovalNavigationAcceptance(profile = FORMAL_PRICE_APPROVAL_NAVIGATION_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.navigationStepCount === 5 && profile.roleViewCount === 3
    && profile.navigationMeansExecution === false && profile.userPathMeansWorkflowRuntime === false
    && profile.nextStepMeansAutoAction === false && profile.routeActionEnabled === false
    && profile.workflowRuntimeConnected === false && profile.autoActionEnabled === false
    && profile.approvalObjectCount === 0 && profile.approvalTaskCount === 0
    && profile.businessWriteCount === 0 && profile.databaseState === 'UNCHANGED' && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
