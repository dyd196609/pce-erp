export const FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_VERSION = 'V1.14.2.8.7.6'

export const FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze([
    'formal-price-approval-view-switcher',
    'formal-price-approval-human-acceptance',
    'formal-price-approval-user-feedback',
  ]),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  canaryEnvironment: 'canary',
  canaryIsProduction: false,
  humanRoleCount: 3,
  feedbackLoopStateCount: 5,
  humanAcceptanceIsBusinessExecution: false,
  feedbackIsErpData: false,
  feedbackPersisted: false,
  approvalObjectCount: 0,
  workflowInstanceCount: 0,
  approvalTaskCount: 0,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalHumanAcceptance(profile = FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_PROFILE) {
  const valid = profile.profileCode === 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE'
    && profile.gates.length === 8 && profile.canaryEnvironment === 'canary'
    && profile.canaryIsProduction === false && profile.humanRoleCount === 3
    && profile.feedbackLoopStateCount === 5 && profile.humanAcceptanceIsBusinessExecution === false
    && profile.feedbackIsErpData === false && profile.feedbackPersisted === false
    && profile.approvalObjectCount === 0 && profile.workflowInstanceCount === 0
    && profile.approvalTaskCount === 0 && profile.businessWriteCount === 0
    && profile.databaseState === 'UNCHANGED' && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
