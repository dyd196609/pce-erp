export const PURCHASE_REQUEST_INQUIRY_MAPPING_RULE_VERSION = 'V1.14.2.8.7.7'

const zeroEffect = Object.freeze({ inquiryCreated: false, supplierSent: false, quotationTaskCreated: false,
  sourceTransactionCreated: false, businessWriteCount: 0, productionDataWritten: false })

export function evaluatePurchaseRequestInquiryMapping(input = {}) {
  if (input.action !== 'validateMapping') {
    return Object.freeze({ result: 'FAIL', decision: 'blocked', mappingStatus: 'not_validated', ...zeroEffect })
  }
  const source = input.source || {}
  const requiredComplete = ['requestNo', 'requestDate', 'requester', 'purchaseDepartment', 'requiredDate', 'currency']
    .every(key => Boolean(source[key])) && Array.isArray(source.details) && source.details.length > 0
  const sourceEligible = ['approved', 'converted'].includes(source.statusCode)
  const valid = requiredComplete && sourceEligible && input.productionMode !== true && input.persistRequested !== true
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', decision: valid ? 'mapping_validated' : 'blocked',
    mappingStatus: valid ? 'mapping_ready' : 'blocked', sourceTraceEstablished: Boolean(source.requestNo),
    ...zeroEffect })
}
