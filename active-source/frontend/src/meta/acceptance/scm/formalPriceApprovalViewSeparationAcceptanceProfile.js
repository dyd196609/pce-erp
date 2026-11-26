export const FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_ACCEPTANCE_VERSION = 'V1.14.2.8.7.4'

export const FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['formal-price-approval-view-switcher']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  viewModeCount: 2, defaultMode: 'business_view',
  businessViewMeansAcceptanceView: false, viewSwitchMeansBusinessAction: false, hiddenMeansDeleted: false,
  governanceModelCountPreserved: true, businessActionTriggered: false,
  approvalObjectCount: 0, workflowInstanceCount: 0, businessWriteCount: 0,
  databaseState: 'UNCHANGED', productionDataWritten: false,
})

export function validateFormalPriceApprovalViewSeparationAcceptance(profile = FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.viewModeCount === 2 && profile.defaultMode === 'business_view'
    && profile.businessViewMeansAcceptanceView === false && profile.viewSwitchMeansBusinessAction === false
    && profile.hiddenMeansDeleted === false && profile.governanceModelCountPreserved === true
    && profile.businessActionTriggered === false && profile.approvalObjectCount === 0 && profile.workflowInstanceCount === 0
    && profile.businessWriteCount === 0 && profile.databaseState === 'UNCHANGED' && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
