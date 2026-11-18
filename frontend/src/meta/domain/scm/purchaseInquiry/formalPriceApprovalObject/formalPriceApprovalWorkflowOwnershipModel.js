export const FORMAL_PRICE_APPROVAL_WORKFLOW_OWNERSHIP_VERSION = 'V1.14.2.8.6.18'

export const FORMAL_PRICE_APPROVAL_WORKFLOW_OWNERSHIP = Object.freeze({
  ownershipCode: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_OWNERSHIP',
  version: FORMAL_PRICE_APPROVAL_WORKFLOW_OWNERSHIP_VERSION,
  lifecycleOwner: 'formal_price_approval_lifecycle_domain',
  workflowOwner: 'price_approval_workflow_domain',
  boundaryOwner: 'formal_price_approval_workflow_handoff',
  ownershipTransferMode: 'evidence_only',
  ownershipMeansExecution: false,
  executionAuthorityGranted: false,
  workflowStartAuthorityGranted: false,
  persistenceAuthorityGranted: false,
})

export function validateFormalPriceApprovalWorkflowOwnership(model = FORMAL_PRICE_APPROVAL_WORKFLOW_OWNERSHIP) {
  const valid = model.lifecycleOwner !== model.workflowOwner
    && model.boundaryOwner === 'formal_price_approval_workflow_handoff'
    && model.ownershipTransferMode === 'evidence_only'
    && model.ownershipMeansExecution === false
    && model.executionAuthorityGranted === false
    && model.workflowStartAuthorityGranted === false
    && model.persistenceAuthorityGranted === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
