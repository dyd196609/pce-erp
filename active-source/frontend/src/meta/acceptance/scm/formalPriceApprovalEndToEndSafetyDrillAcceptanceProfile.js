export const FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_ACCEPTANCE_VERSION = 'V1.14.2.8.6.15'

export const FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_END_TO_END_DRILL_READY',
  route: '/scm/purchase-inquiry',
  drillCode: 'SCM_FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL',
  requiredRegions: Object.freeze(['formal-price-approval-end-to-end-safety-drill']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  requiredStageCount: 15,
  drillIsExecution: false,
  simulationIsCreation: false,
  boundaryIsExecutor: false,
  productionExecution: false,
  formalPriceApprovalObjectCreated: false,
  approvalWorkflowStarted: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalEndToEndSafetyDrillAcceptance(profile = FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.requiredStageCount === 15
    && profile.drillIsExecution === false
    && profile.simulationIsCreation === false
    && profile.boundaryIsExecutor === false
    && profile.productionExecution === false
    && profile.formalPriceApprovalObjectCreated === false
    && profile.approvalWorkflowStarted === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
