export const INQUIRY_CREATION_SIMULATION_RULE_VERSION = 'V1.14.2.8.7.8'

const zeroEffect = Object.freeze({ inquiryCreated: false, supplierSent: false,
  supplierInquiryTaskCreated: false, quotationTaskCreated: false, simulationPersisted: false,
  businessWriteCount: 0, productionDataWritten: false })

export function evaluateInquiryCreationSimulation(input = {}) {
  if (input.action === 'simulateInquiryCreation') {
    const projection = input.projection || {}
    const ready = input.mappingStatus === 'mapping_ready'
      && Boolean(projection.sourceRequestNo) && Boolean(projection.requiredDate)
      && Boolean(projection.currency) && Array.isArray(projection.inquiryLines)
      && projection.inquiryLines.length > 0 && projection.isInquiry === false
      && input.productionMode !== true && input.persistRequested !== true
    return Object.freeze({ result: ready ? 'PASS' : 'FAIL', decision: ready ? 'simulation_ready' : 'blocked',
      simulationStatus: ready ? 'simulated_ready' : 'blocked', ...zeroEffect })
  }
  if (input.action === 'prepareSupplierCandidates') {
    const candidates = Array.isArray(input.supplierCandidates) ? input.supplierCandidates : []
    const ready = input.simulationStatus === 'simulated_ready' && candidates.length > 0
      && candidates.every(candidate => Boolean(candidate.supplierId) && Boolean(candidate.evidenceReference))
      && input.createTaskRequested !== true && input.sendRequested !== true
    return Object.freeze({ result: ready ? 'PASS' : 'FAIL', decision: ready ? 'supplier_preparation_ready' : 'blocked',
      preparationStatus: ready ? 'prepared' : 'blocked', ...zeroEffect })
  }
  return Object.freeze({ result: 'FAIL', decision: 'blocked', ...zeroEffect })
}
