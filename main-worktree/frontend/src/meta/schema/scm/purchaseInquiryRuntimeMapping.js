export const PURCHASE_INQUIRY_RUNTIME_MAPPING_VERSION = 'V1.14.2.8.6.0'

const mapField = (runtimeField, sourceFields, fallback = '') => Object.freeze({
  runtimeField,
  sourceFields: Object.freeze(sourceFields),
  fallback,
  factAuthority: 'server',
})

export const PURCHASE_INQUIRY_RUNTIME_MAPPING = Object.freeze({
  mappingCode: 'SCM_PURCHASE_INQUIRY_RUNTIME_MAPPING',
  version: PURCHASE_INQUIRY_RUNTIME_MAPPING_VERSION,
  pageCode: 'purchase-inquiry',
  schemaId: 'PurchaseInquirySchema',
  businessObject: 'PurchaseInquiry',
  source: 'server_facts',
  fields: Object.freeze([
    mapField('id', ['id']),
    mapField('inquiryNo', ['inquiryNo', 'businessNo']),
    mapField('inquiryTitle', ['inquiryTitle', 'title']),
    mapField('inquiryDate', ['inquiryDate', 'createdDate']),
    mapField('sourceRequestNo', ['sourceRequestNo', 'sourceObjectNo']),
    mapField('buyerName', ['buyerName', 'buyer']),
    mapField('supplierCount', ['supplierCount'], 0),
    mapField('lineCount', ['lineCount', 'materialCount'], 0),
    mapField('currency', ['currency'], 'CNY'),
    mapField('statusCode', ['statusCode', 'status']),
    mapField('statusLabel', ['statusLabel']),
    mapField('runtimeState', ['runtimeState'], 'inquiry_draft'),
    mapField('lines', ['lines', 'materialLines', 'items'], Object.freeze([])),
    mapField('suppliers', ['suppliers', 'supplierCandidates'], Object.freeze([])),
    mapField('supplierSendStatus', ['supplierSendStatus'], 'pending'),
    mapField('supplierSendStatusLabel', ['supplierSendStatusLabel'], '待发送'),
    mapField('quoteReceiveStatus', ['quoteReceiveStatus'], 'pending'),
    mapField('quoteReceiveStatusLabel', ['quoteReceiveStatusLabel'], '待接收'),
    mapField('sourceEvidence', ['sourceEvidence'], Object.freeze({})),
  ]),
  statusPresentation: Object.freeze({ visibleField: 'statusLabel', internalField: 'statusCode' }),
  writeBoundary: Object.freeze({ persistence: 'none', database: false, productionData: false }),
})

function firstDefined(source, keys, fallback) {
  for (const key of keys) {
    if (source?.[key] !== undefined && source[key] !== null && source[key] !== '') return source[key]
  }
  return fallback
}

export function mapPurchaseInquiryServerFact(source = {}) {
  return Object.freeze(Object.fromEntries(PURCHASE_INQUIRY_RUNTIME_MAPPING.fields.map((mapping) => [
    mapping.runtimeField,
    firstDefined(source, mapping.sourceFields, mapping.fallback),
  ])))
}

export function validatePurchaseInquiryRuntimeMapping(mapping = PURCHASE_INQUIRY_RUNTIME_MAPPING) {
  const required = ['id', 'inquiryNo', 'inquiryDate', 'sourceRequestNo', 'supplierCount', 'lineCount',
    'statusCode', 'statusLabel', 'runtimeState', 'lines', 'suppliers', 'supplierSendStatus',
    'quoteReceiveStatus', 'sourceEvidence']
  const mapped = new Set(mapping.fields?.map((item) => item.runtimeField))
  const missing = required.filter((field) => !mapped.has(field))
  const valid = mapping.source === 'server_facts'
    && mapping.statusPresentation?.visibleField === 'statusLabel'
    && mapping.writeBoundary?.database === false
    && missing.length === 0
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid, missing: Object.freeze(missing) })
}
