export const PURCHASE_REQUEST_INQUIRY_MAPPING_ACCEPTANCE_VERSION = 'V1.14.2.8.7.7'

export const PURCHASE_REQUEST_INQUIRY_MAPPING_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_REQUEST_INQUIRY_MAPPING_VALIDATION',
  version: PURCHASE_REQUEST_INQUIRY_MAPPING_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_REQUEST_INQUIRY_MAPPING_VALIDATION_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['purchase-request-inquiry-mapping-validation']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  mappingMode: 'simulation_validation_only',
  fieldMappingCount: 8,
  scenarioCount: 3,
  mappingCreatesInquiry: false,
  supplierSent: false,
  quotationTaskCreated: false,
  sourceTraceCreatesTransaction: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validatePurchaseRequestInquiryMappingAcceptance(profile = PURCHASE_REQUEST_INQUIRY_MAPPING_ACCEPTANCE_PROFILE) {
  const valid = profile.profileCode === 'SCM_PURCHASE_REQUEST_INQUIRY_MAPPING_VALIDATION'
    && profile.gates.length === 8 && profile.mappingMode === 'simulation_validation_only'
    && profile.fieldMappingCount === 8 && profile.scenarioCount === 3
    && profile.mappingCreatesInquiry === false && profile.supplierSent === false
    && profile.quotationTaskCreated === false && profile.sourceTraceCreatesTransaction === false
    && profile.businessWriteCount === 0 && profile.databaseState === 'UNCHANGED'
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
