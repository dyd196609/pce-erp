export const PURCHASE_REQUEST_INQUIRY_MAPPING_GUARD_VERSION = 'V1.14.2.8.7.7'

export const PURCHASE_REQUEST_INQUIRY_MAPPING_FORBIDDEN_ACTIONS = Object.freeze([
  'createInquiryFromMapping', 'sendSupplierFromMapping', 'createQuotationTaskFromMapping',
  'persistMappingProjection', 'treatSourceTraceAsTransaction', 'writeProductionDatabase',
])

const zeroEffect = Object.freeze({ inquiryCreated: false, supplierSent: false, quotationTaskCreated: false,
  sourceTransactionCreated: false, mappingPersisted: false, businessWriteCount: 0, productionDataWritten: false })

export function evaluatePurchaseRequestInquiryMappingGuard({ action = '', mode = '' } = {}) {
  if (action === 'validateReadOnlyMapping') {
    const allowed = mode === 'simulation_validation_only'
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow_validation_only' : 'deny', ...zeroEffect })
  }
  const forbidden = PURCHASE_REQUEST_INQUIRY_MAPPING_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: forbidden ? 'PASS' : 'FAIL', decision: 'deny',
    reason: forbidden ? 'purchase_request_inquiry_mapping_effect_frozen' : 'mapping_default_deny', ...zeroEffect })
}
