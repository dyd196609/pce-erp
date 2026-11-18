export const INQUIRY_CREATION_SIMULATION_GUARD_VERSION = 'V1.14.2.8.7.8'

export const INQUIRY_CREATION_SIMULATION_FORBIDDEN_ACTIONS = Object.freeze([
  'createInquiryFromSimulation', 'sendSupplierFromPreparation', 'createSupplierInquiryTaskFromCandidate',
  'createQuotationTaskFromPreparation', 'persistSimulation', 'persistSupplierPreparation',
  'writeProductionDatabase',
])

const zeroEffect = Object.freeze({ inquiryCreated: false, supplierSent: false,
  supplierInquiryTaskCreated: false, quotationTaskCreated: false, simulationPersisted: false,
  preparationPersisted: false, businessWriteCount: 0, productionDataWritten: false })

export function evaluateInquiryCreationSimulationGuard({ action = '', mode = '' } = {}) {
  if (action === 'runPreparationValidation') {
    const allowed = mode === 'simulation_only'
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow_simulation_only' : 'deny', ...zeroEffect })
  }
  const forbidden = INQUIRY_CREATION_SIMULATION_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: forbidden ? 'PASS' : 'FAIL', decision: 'deny',
    reason: forbidden ? 'inquiry_creation_and_supplier_execution_frozen' : 'simulation_default_deny', ...zeroEffect })
}
