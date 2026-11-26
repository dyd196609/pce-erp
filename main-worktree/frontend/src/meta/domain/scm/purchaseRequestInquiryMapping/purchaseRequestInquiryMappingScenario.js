export const PURCHASE_REQUEST_INQUIRY_MAPPING_SCENARIO_VERSION = 'V1.14.2.8.7.7'

export const PURCHASE_REQUEST_INQUIRY_MAPPING_SCENARIOS = Object.freeze([
  Object.freeze({ scenarioId: 'normal_approved_request', scenarioType: 'normal', sourceStatus: 'approved',
    requiredFieldsComplete: true, lineCount: 2, expectedResult: 'mapping_ready', usesProductionData: false }),
  Object.freeze({ scenarioId: 'special_preferred_supplier_trace', scenarioType: 'special', sourceStatus: 'approved',
    requiredFieldsComplete: true, lineCount: 1, expectedResult: 'mapping_ready_with_supplier_trace', usesProductionData: false }),
  Object.freeze({ scenarioId: 'exception_missing_lines', scenarioType: 'exception', sourceStatus: 'approved',
    requiredFieldsComplete: false, lineCount: 0, expectedResult: 'blocked', usesProductionData: false }),
])

export function validatePurchaseRequestInquiryMappingScenarios(scenarios = PURCHASE_REQUEST_INQUIRY_MAPPING_SCENARIOS) {
  const valid = scenarios.length === 3
    && scenarios.map(item => item.scenarioType).join('|') === 'normal|special|exception'
    && scenarios.every(item => item.usesProductionData === false)
    && scenarios[0].expectedResult === 'mapping_ready'
    && scenarios[1].expectedResult === 'mapping_ready_with_supplier_trace'
    && scenarios[2].expectedResult === 'blocked'
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid, scenarioCount: scenarios.length })
}
