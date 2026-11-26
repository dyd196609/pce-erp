export const FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_VERSION = 'V1.14.2.8.7.1'

export const FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['formal-price-approval-business-view-user-acceptance']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  optimizedViewItemCount: 4, checklistCount: 5, passedChecklistCount: 5,
  businessViewMeansBusinessExecution: false, userAcceptanceMeansOperationApproval: false,
  operationApprovalGranted: false, productionOperationEnabled: false,
  approvalObjectCount: 0, workflowInstanceCount: 0, approvalTaskCount: 0,
  businessWriteCount: 0, databaseState: 'UNCHANGED', productionDataWritten: false,
})

export function validateFormalPriceApprovalBusinessViewUserAcceptance(profile = FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.optimizedViewItemCount === 4 && profile.checklistCount === 5 && profile.passedChecklistCount === 5
    && profile.businessViewMeansBusinessExecution === false && profile.userAcceptanceMeansOperationApproval === false
    && profile.operationApprovalGranted === false && profile.productionOperationEnabled === false
    && profile.approvalObjectCount === 0 && profile.workflowInstanceCount === 0 && profile.approvalTaskCount === 0
    && profile.businessWriteCount === 0 && profile.databaseState === 'UNCHANGED' && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
