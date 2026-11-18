export const FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_VERSION = 'V1.14.2.8.6.18'

export const FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_STATUSES = Object.freeze([
  'not_assessed',
  'checking',
  'handoff_ready',
  'blocked',
])

export const FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF = Object.freeze({
  handoffCode: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF',
  version: FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_VERSION,
  sourceDomain: 'formal_price_approval_lifecycle',
  targetDomain: 'price_approval_workflow',
  status: 'not_assessed',
  mode: 'boundary_design_only',
  lifecycleIsWorkflow: false,
  handoffMeansWorkflowStart: false,
  pendingApprovalMeansWorkflowStarted: false,
  workflowEngineConnected: false,
  workflowInstanceCount: 0,
  approvalTaskCount: 0,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalWorkflowHandoff(model = FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF) {
  const valid = model.handoffCode === 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF'
    && FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_STATUSES.includes(model.status)
    && model.sourceDomain !== model.targetDomain
    && model.mode === 'boundary_design_only'
    && model.lifecycleIsWorkflow === false
    && model.handoffMeansWorkflowStart === false
    && model.pendingApprovalMeansWorkflowStarted === false
    && model.workflowEngineConnected === false
    && model.workflowInstanceCount === 0
    && model.approvalTaskCount === 0
    && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
