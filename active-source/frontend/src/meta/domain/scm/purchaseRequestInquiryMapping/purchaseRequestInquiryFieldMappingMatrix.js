export const PURCHASE_REQUEST_INQUIRY_FIELD_MAPPING_MATRIX_VERSION = 'V1.14.2.8.7.7'

const field = (sourceField, targetField, required, mappingRule) => Object.freeze({
  sourceField, targetField, required, mappingRule, transformationMode: 'read_only_projection',
})

export const PURCHASE_REQUEST_INQUIRY_FIELD_MAPPING_MATRIX = Object.freeze([
  field('requestNo', 'sourceRequestNo', true, 'direct_reference'),
  field('requestDate', 'sourceRequestDate', true, 'direct_copy'),
  field('requester', 'requester', true, 'direct_copy'),
  field('purchaseDepartment', 'buyerDepartment', true, 'direct_copy'),
  field('requiredDate', 'requiredDate', true, 'direct_copy'),
  field('currency', 'currency', true, 'direct_copy'),
  field('details', 'inquiryLines', true, 'immutable_line_projection'),
  field('preferredSupplierId', 'supplierCandidateReference', false, 'trace_reference_only'),
])

export function validatePurchaseRequestInquiryFieldMappingMatrix(matrix = PURCHASE_REQUEST_INQUIRY_FIELD_MAPPING_MATRIX) {
  const valid = matrix.length === 8 && matrix.filter(item => item.required).length === 7
    && matrix.every(item => Boolean(item.sourceField) && Boolean(item.targetField)
      && item.transformationMode === 'read_only_projection')
    && matrix.some(item => item.sourceField === 'requestNo' && item.targetField === 'sourceRequestNo')
    && matrix.some(item => item.sourceField === 'details' && item.targetField === 'inquiryLines')
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid, fieldCount: matrix.length })
}
