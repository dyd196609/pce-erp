export const FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_MODEL_VERSION = 'V1.14.2.8.6.8'

export const FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_STATES = Object.freeze([
  'not_started',
  'checking',
  'simulated_ready',
  'blocked',
  'completed',
])

export const FORMAL_PRICE_APPROVAL_CREATION_SIMULATION = Object.freeze({
  simulationCode: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_SIMULATION',
  version: FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_MODEL_VERSION,
  artifactType: 'NON_PERSISTENT_SIMULATION',
  businessObject: false,
  formalPriceApprovalObject: false,
  lifecycle: FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_STATES,
  initialStatus: 'not_started',
  terminalStatuses: Object.freeze(['blocked', 'completed']),
  persistenceMode: 'none',
  databaseWriteAllowed: false,
  businessWriteCount: 0,
})

export function validateFormalPriceApprovalCreationSimulation(model = FORMAL_PRICE_APPROVAL_CREATION_SIMULATION) {
  const valid = model.simulationCode === 'SCM_FORMAL_PRICE_APPROVAL_CREATION_SIMULATION'
    && model.artifactType === 'NON_PERSISTENT_SIMULATION'
    && model.businessObject === false
    && model.formalPriceApprovalObject === false
    && model.lifecycle.join(',') === 'not_started,checking,simulated_ready,blocked,completed'
    && model.persistenceMode === 'none'
    && model.databaseWriteAllowed === false
    && model.businessWriteCount === 0
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
