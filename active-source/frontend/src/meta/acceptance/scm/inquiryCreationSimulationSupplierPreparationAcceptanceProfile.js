export const INQUIRY_CREATION_SIMULATION_SUPPLIER_PREPARATION_ACCEPTANCE_VERSION = 'V1.14.2.8.7.8'

export const INQUIRY_CREATION_SIMULATION_SUPPLIER_PREPARATION_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_INQUIRY_CREATION_SIMULATION_SUPPLIER_PREPARATION',
  version: INQUIRY_CREATION_SIMULATION_SUPPLIER_PREPARATION_ACCEPTANCE_VERSION,
  status: 'SCM_INQUIRY_CREATION_SIMULATION_SUPPLIER_PREPARATION_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['inquiry-creation-simulation-supplier-preparation']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  simulationMode: 'simulation_only',
  prerequisiteCheckCount: 4,
  supplierCandidateCount: 2,
  inquiryCreated: false,
  supplierSent: false,
  supplierInquiryTaskCreated: false,
  quotationTaskCreated: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateInquiryCreationSimulationSupplierPreparationAcceptance(profile = INQUIRY_CREATION_SIMULATION_SUPPLIER_PREPARATION_ACCEPTANCE_PROFILE) {
  const valid = profile.profileCode === 'SCM_INQUIRY_CREATION_SIMULATION_SUPPLIER_PREPARATION'
    && profile.gates.length === 8 && profile.simulationMode === 'simulation_only'
    && profile.prerequisiteCheckCount === 4 && profile.supplierCandidateCount === 2
    && profile.inquiryCreated === false && profile.supplierSent === false
    && profile.supplierInquiryTaskCreated === false && profile.quotationTaskCreated === false
    && profile.businessWriteCount === 0 && profile.databaseState === 'UNCHANGED'
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
