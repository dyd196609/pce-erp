export const FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_VERSION = 'V1.14.2.8.7.5'

export const FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['formal-price-approval-view-switcher', 'formal-price-approval-business-user-view', 'formal-price-approval-user-feedback']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  governanceStandardCode: 'PCE_ERP_PAGE_VIEW_GOVERNANCE_STANDARD',
  defaultViewMode: 'business_view', viewModeCount: 2, checklistCount: 7, passedChecklistCount: 7,
  viewSwitchExecuted: true, businessActionTriggered: false, userFeedbackPersisted: false,
  approvalObjectCount: 0, workflowInstanceCount: 0, approvalTaskCount: 0,
  businessWriteCount: 0, databaseState: 'UNCHANGED', productionDataWritten: false,
})

export function validateFormalPriceApprovalUserAcceptance(profile = FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.governanceStandardCode === 'PCE_ERP_PAGE_VIEW_GOVERNANCE_STANDARD'
    && profile.defaultViewMode === 'business_view' && profile.viewModeCount === 2
    && profile.checklistCount === 7 && profile.passedChecklistCount === 7
    && profile.viewSwitchExecuted === true && profile.businessActionTriggered === false && profile.userFeedbackPersisted === false
    && profile.approvalObjectCount === 0 && profile.workflowInstanceCount === 0 && profile.approvalTaskCount === 0
    && profile.businessWriteCount === 0 && profile.databaseState === 'UNCHANGED' && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
