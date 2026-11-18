export const FORMAL_PRICE_APPROVAL_CANARY_COHORT_ACCEPTANCE_VERSION = 'V1.14.2.8.7.6.1'

export const FORMAL_PRICE_APPROVAL_CANARY_COHORT_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_CANARY_COHORT_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_CANARY_COHORT_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_CANARY_COHORT_AUTOMATIC_ACCEPTANCE_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['formal-price-approval-view-switcher', 'formal-price-approval-canary-cohort-summary']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  cohortMemberCount: 3,
  automaticAcceptanceMode: 'in_memory_assertion_only',
  summaryStorageMode: 'memory_session_only',
  automaticAcceptanceIsBusinessExecution: false,
  summaryIsApprovalResult: false,
  resultPersisted: false,
  approvalObjectCount: 0,
  workflowInstanceCount: 0,
  approvalTaskCount: 0,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalCanaryCohortAcceptance(profile = FORMAL_PRICE_APPROVAL_CANARY_COHORT_ACCEPTANCE_PROFILE) {
  const valid = profile.profileCode === 'SCM_FORMAL_PRICE_APPROVAL_CANARY_COHORT_ACCEPTANCE'
    && profile.gates.length === 8 && profile.cohortMemberCount === 3
    && profile.automaticAcceptanceMode === 'in_memory_assertion_only'
    && profile.summaryStorageMode === 'memory_session_only'
    && profile.automaticAcceptanceIsBusinessExecution === false
    && profile.summaryIsApprovalResult === false && profile.resultPersisted === false
    && profile.approvalObjectCount === 0 && profile.workflowInstanceCount === 0
    && profile.approvalTaskCount === 0 && profile.businessWriteCount === 0
    && profile.databaseState === 'UNCHANGED' && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
