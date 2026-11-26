export const FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_ACCEPTANCE_VERSION = 'V1.14.2.8.6.8'

export const FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_READY',
  route: '/scm/purchase-inquiry',
  simulationCode: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_SIMULATION',
  executorCode: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_ZERO_WRITE_EXECUTOR',
  requiredRegions: Object.freeze(['formal-price-approval-creation-simulation']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  simulationIsBusinessObject: false,
  persistenceAdapterConnected: false,
  formalPriceApprovalObjectCreated: false,
  approvalWorkflowStarted: false,
  approvalTaskCreated: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalCreationSimulationAcceptance(profile = FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.simulationIsBusinessObject === false
    && profile.persistenceAdapterConnected === false
    && profile.formalPriceApprovalObjectCreated === false
    && profile.approvalWorkflowStarted === false
    && profile.approvalTaskCreated === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
