export const PURCHASE_REQUEST_INQUIRY_MAPPING_VERSION = 'V1.14.2.8.7.7'

export const PURCHASE_REQUEST_INQUIRY_MAPPING = Object.freeze({
  modelCode: 'SCM_PURCHASE_REQUEST_INQUIRY_MAPPING_VALIDATION',
  version: PURCHASE_REQUEST_INQUIRY_MAPPING_VERSION,
  sourceObject: 'PurchaseRequest',
  targetObject: 'InquiryPreparationProjection',
  mappingMode: 'simulation_validation_only',
  sourceTraceMode: 'reference_only',
  status: 'validation_ready',
  createsInquiry: false,
  sendsSupplier: false,
  createsQuotationTask: false,
  persisted: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function createPurchaseRequestInquiryPreparationProjection(source = {}) {
  return Object.freeze({
    mappingValidationNo: `MAP-${String(source.requestNo || 'UNRESOLVED')}`,
    sourceRequestNo: String(source.requestNo || ''),
    sourceRequestDate: String(source.requestDate || ''),
    requester: String(source.requester || ''),
    buyerDepartment: String(source.purchaseDepartment || ''),
    requiredDate: String(source.requiredDate || ''),
    currency: String(source.currency || ''),
    inquiryLines: Object.freeze(Array.isArray(source.details) ? source.details.map(item => Object.freeze({ ...item })) : []),
    supplierCandidateReference: source.preferredSupplierId || null,
    projectionType: 'InquiryPreparationProjection',
    isInquiry: false,
    persistenceMode: 'none',
    sourceTraceOnly: true,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export function validatePurchaseRequestInquiryMapping(model = PURCHASE_REQUEST_INQUIRY_MAPPING) {
  const valid = model.modelCode === 'SCM_PURCHASE_REQUEST_INQUIRY_MAPPING_VALIDATION'
    && model.sourceObject === 'PurchaseRequest' && model.targetObject === 'InquiryPreparationProjection'
    && model.mappingMode === 'simulation_validation_only' && model.sourceTraceMode === 'reference_only'
    && model.createsInquiry === false && model.sendsSupplier === false
    && model.createsQuotationTask === false && model.persisted === false
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
