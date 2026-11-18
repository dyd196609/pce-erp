export const FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_ACCEPTANCE_VERSION = 'V1.14.2.8.6.25'

export const FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['formal-price-approval-governance-summary']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  governanceSummaryMeansExecution: false, validationMeansOperation: false, passMeansAutoRun: false,
  stageCount: 12, passedStageCount: 12, executionEnabledStageCount: 0,
  operationEnabled: false, autoRunEnabled: false, approvalObjectCount: 0, workflowInstanceCount: 0, approvalTaskCount: 0,
  businessWriteCount: 0, databaseState: 'UNCHANGED', productionDataWritten: false,
})

export function validateFormalPriceApprovalGovernanceSummaryAcceptance(profile = FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.governanceSummaryMeansExecution === false && profile.validationMeansOperation === false && profile.passMeansAutoRun === false
    && profile.stageCount === 12 && profile.passedStageCount === 12 && profile.executionEnabledStageCount === 0
    && profile.operationEnabled === false && profile.autoRunEnabled === false
    && profile.approvalObjectCount === 0 && profile.workflowInstanceCount === 0 && profile.approvalTaskCount === 0
    && profile.businessWriteCount === 0 && profile.databaseState === 'UNCHANGED' && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
