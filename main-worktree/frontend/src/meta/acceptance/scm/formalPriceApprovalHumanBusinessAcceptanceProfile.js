export const FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_VERSION = 'V1.14.2.8.7.6.2'

export const FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze([
    'formal-price-approval-recent-canary-result',
    'formal-price-approval-human-business-acceptance-execution',
    'formal-price-approval-human-feedback-collection',
  ]),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  recentCanaryResult: 'PASS',
  recentCanaryTotalCount: 3,
  recentCanaryPassCount: 3,
  recentCanaryFailCount: 0,
  roleCount: 3,
  checklistCount: 7,
  humanAcceptanceExecuted: true,
  businessExecutionTriggered: false,
  feedbackPersisted: false,
  approvalObjectCount: 0,
  workflowInstanceCount: 0,
  approvalTaskCount: 0,
  businessStateChanged: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalHumanBusinessAcceptance(profile = FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_PROFILE) {
  const valid = profile.profileCode === 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE'
    && profile.gates.length === 8 && profile.recentCanaryResult === 'PASS'
    && profile.recentCanaryTotalCount === 3 && profile.recentCanaryPassCount === 3
    && profile.recentCanaryFailCount === 0 && profile.roleCount === 3 && profile.checklistCount === 7
    && profile.humanAcceptanceExecuted === true && profile.businessExecutionTriggered === false
    && profile.feedbackPersisted === false && profile.approvalObjectCount === 0
    && profile.workflowInstanceCount === 0 && profile.approvalTaskCount === 0
    && profile.businessStateChanged === false && profile.businessWriteCount === 0
    && profile.databaseState === 'UNCHANGED' && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
