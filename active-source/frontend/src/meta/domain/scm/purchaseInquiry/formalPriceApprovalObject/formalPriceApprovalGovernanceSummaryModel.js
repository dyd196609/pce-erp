import { FORMAL_PRICE_APPROVAL_GOVERNANCE_STAGE_MATRIX } from './formalPriceApprovalGovernanceStageMatrix.js'

export const FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_VERSION = 'V1.14.2.8.6.25'

export const FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY = Object.freeze({
  summaryCode: 'SCM_FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY',
  version: FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_VERSION,
  matrixCode: FORMAL_PRICE_APPROVAL_GOVERNANCE_STAGE_MATRIX.matrixCode,
  summaryStatus: 'validation_ready',
  governanceSummaryMeansExecution: false,
  passMeansAutoRun: false,
  stageCount: 12,
  passedStageCount: 12,
  executionEnabledStageCount: 0,
  approvalObjectCount: 0,
  workflowInstanceCount: 0,
  approvalTaskCount: 0,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalGovernanceSummary(model = FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY) {
  const valid = model.summaryCode === 'SCM_FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY'
    && model.matrixCode === 'SCM_FORMAL_PRICE_APPROVAL_GOVERNANCE_STAGE_MATRIX'
    && model.summaryStatus === 'validation_ready'
    && model.governanceSummaryMeansExecution === false && model.passMeansAutoRun === false
    && model.stageCount === 12 && model.passedStageCount === 12 && model.executionEnabledStageCount === 0
    && model.approvalObjectCount === 0 && model.workflowInstanceCount === 0 && model.approvalTaskCount === 0
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
