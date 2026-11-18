export const FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_RULE_VERSION = 'V1.14.2.8.6.18'

export function evaluateFormalPriceApprovalWorkflowHandoff(input = {}) {
  if (input.assessmentRequested !== true) {
    return Object.freeze({ result: 'PASS', decision: 'not_assessed', handoffStatus: 'not_assessed', workflowStarted: false, workflowInstanceCreated: false, approvalTaskCreated: false, stateChanged: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const evidenceComplete = input.lifecycleState === 'pending_approval'
    && input.lifecycleEvidenceComplete === true
    && input.ownershipEvidenceComplete === true
  const forbiddenRequest = input.workflowStartRequested === true
    || input.workflowInstanceCreationRequested === true
    || input.approvalTaskCreationRequested === true
    || input.executionRequested === true
    || input.persistenceRequested === true
    || Number(input.businessWriteCount || 0) > 0
  const handoffStatus = evidenceComplete && !forbiddenRequest ? 'handoff_ready' : 'blocked'
  return Object.freeze({
    result: handoffStatus === 'handoff_ready' ? 'PASS' : 'FAIL',
    decision: handoffStatus,
    handoffStatus,
    lifecycleState: input.lifecycleState || '',
    ownershipEvidenceOnly: true,
    workflowStarted: false,
    workflowInstanceCreated: false,
    approvalTaskCreated: false,
    executionPerformed: false,
    stateChanged: false,
    persistencePerformed: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
