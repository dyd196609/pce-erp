export const INQUIRY_CREATION_SIMULATION_VERSION = 'V1.14.2.8.7.8'

export const INQUIRY_CREATION_SIMULATION_STATES = Object.freeze([
  'not_started', 'checking', 'simulated_ready', 'blocked', 'completed',
])

export function createInquiryCreationSimulation(projection = {}) {
  const checks = Object.freeze({
    sourceTraceComplete: Boolean(projection.sourceRequestNo),
    requiredDateComplete: Boolean(projection.requiredDate),
    currencyComplete: Boolean(projection.currency),
    inquiryLinesComplete: Array.isArray(projection.inquiryLines) && projection.inquiryLines.length > 0,
  })
  const ready = Object.values(checks).every(Boolean) && projection.isInquiry === false
  return Object.freeze({
    modelCode: 'SCM_INQUIRY_CREATION_SIMULATION',
    version: INQUIRY_CREATION_SIMULATION_VERSION,
    simulationNo: `SIM-${String(projection.mappingValidationNo || 'UNRESOLVED')}`,
    mappingValidationNo: String(projection.mappingValidationNo || ''),
    sourceRequestNo: String(projection.sourceRequestNo || ''),
    simulationStatus: ready ? 'simulated_ready' : 'blocked',
    prerequisiteChecks: checks,
    simulatedLineCount: Array.isArray(projection.inquiryLines) ? projection.inquiryLines.length : 0,
    simulatedInquiryReference: ready ? `SIM-INQUIRY-${projection.sourceRequestNo}` : null,
    simulatedObjectType: 'InquiryCreationPreview',
    isInquiry: false,
    inquiryCreated: false,
    persistenceMode: 'none',
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export function validateInquiryCreationSimulation(model) {
  const valid = model?.modelCode === 'SCM_INQUIRY_CREATION_SIMULATION'
    && INQUIRY_CREATION_SIMULATION_STATES.includes(model.simulationStatus)
    && model.simulatedObjectType === 'InquiryCreationPreview'
    && model.isInquiry === false && model.inquiryCreated === false
    && model.persistenceMode === 'none' && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
