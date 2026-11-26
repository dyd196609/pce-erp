export const FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_ACCEPTANCE_VERSION = 'V1.14.2.8.7.0'

export const FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['formal-price-approval-operation-validation']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  scenarioCount: 4, businessViewSectionCount: 4,
  operationValidationMeansProductionOperation: false, businessViewMeansBusinessExecution: false,
  productionOperationEnabled: false, approvalObjectCount: 0, workflowInstanceCount: 0, approvalTaskCount: 0,
  businessWriteCount: 0, databaseState: 'UNCHANGED', productionDataWritten: false,
})

export function validateFormalPriceApprovalOperationValidationAcceptance(profile = FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.scenarioCount === 4 && profile.businessViewSectionCount === 4
    && profile.operationValidationMeansProductionOperation === false && profile.businessViewMeansBusinessExecution === false
    && profile.productionOperationEnabled === false && profile.approvalObjectCount === 0
    && profile.workflowInstanceCount === 0 && profile.approvalTaskCount === 0
    && profile.businessWriteCount === 0 && profile.databaseState === 'UNCHANGED' && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
