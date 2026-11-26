export const FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_ACCEPTANCE_VERSION = 'V1.14.2.8.6.14'

export const FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_READY',
  route: '/scm/purchase-inquiry',
  boundaryCode: 'SCM_FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY',
  contextCode: 'SCM_FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT',
  requiredRegions: Object.freeze(['formal-price-approval-execution-boundary']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  approvedMeansAutoExecute: false,
  boundaryIsExecutor: false,
  productionExecution: false,
  executionPermissionGranted: false,
  formalPriceApprovalObjectCreated: false,
  approvalWorkflowStarted: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalExecutionBoundaryAcceptance(profile = FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.approvedMeansAutoExecute === false
    && profile.boundaryIsExecutor === false
    && profile.productionExecution === false
    && profile.executionPermissionGranted === false
    && profile.formalPriceApprovalObjectCreated === false
    && profile.approvalWorkflowStarted === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
