export const SUPPLIER_QUOTATION_RUNTIME_MAPPING_VERSION = 'V1.14.2.8.6.1'

const mapping = (runtimeField, sourceFields, fallback = '') => Object.freeze({
  runtimeField,
  sourceFields: Object.freeze(sourceFields),
  fallback,
  factAuthority: 'server',
})

export const SUPPLIER_INQUIRY_TASK_RUNTIME_MAPPING = Object.freeze({
  mappingCode: 'SCM_SUPPLIER_INQUIRY_TASK_RUNTIME_MAPPING',
  version: SUPPLIER_QUOTATION_RUNTIME_MAPPING_VERSION,
  sourceCollection: 'supplierInquiryTasks',
  source: 'server_facts',
  fields: Object.freeze([
    mapping('inquiryNo', ['inquiryNo']),
    mapping('supplierId', ['supplierId', 'supplierCode']),
    mapping('sendStatus', ['sendStatus']),
    mapping('sendStatusLabel', ['sendStatusLabel']),
    mapping('responseDeadline', ['responseDeadline']),
    mapping('quotationStatus', ['quotationStatus']),
    mapping('quotationStatusLabel', ['quotationStatusLabel']),
  ]),
})

export const SUPPLIER_QUOTATION_RUNTIME_MAPPING = Object.freeze({
  mappingCode: 'SCM_SUPPLIER_QUOTATION_RUNTIME_MAPPING',
  version: SUPPLIER_QUOTATION_RUNTIME_MAPPING_VERSION,
  sourceCollection: 'supplierQuotations',
  source: 'server_facts',
  fields: Object.freeze([
    mapping('quotationNo', ['quotationNo', 'quoteNo']),
    mapping('supplierId', ['supplierId', 'supplierCode']),
    mapping('inquiryNo', ['inquiryNo']),
    mapping('quotationStatus', ['quotationStatus', 'status']),
    mapping('quotationStatusLabel', ['quotationStatusLabel', 'statusLabel']),
    mapping('items', ['items', 'lines'], []),
    mapping('price', ['price', 'totalQuoteAmount'], 0),
    mapping('currency', ['currency'], 'CNY'),
    mapping('deliveryDays', ['deliveryDays'], 0),
    mapping('validUntil', ['validUntil']),
  ]),
})

function project(source, definition) {
  return Object.freeze(Object.fromEntries(definition.fields.map((field) => {
    const sourceField = field.sourceFields.find((name) => source?.[name] !== undefined && source[name] !== null)
    return [field.runtimeField, sourceField ? source[sourceField] : field.fallback]
  })))
}

export const mapSupplierInquiryTaskFact = (source = {}) => project(source, SUPPLIER_INQUIRY_TASK_RUNTIME_MAPPING)
export const mapSupplierQuotationFact = (source = {}) => project(source, SUPPLIER_QUOTATION_RUNTIME_MAPPING)

export function validateSupplierQuotationRuntimeMappings() {
  const taskFields = new Set(SUPPLIER_INQUIRY_TASK_RUNTIME_MAPPING.fields.map((field) => field.runtimeField))
  const quotationFields = new Set(SUPPLIER_QUOTATION_RUNTIME_MAPPING.fields.map((field) => field.runtimeField))
  const valid = ['inquiryNo', 'supplierId', 'sendStatus', 'responseDeadline', 'quotationStatus'].every((field) => taskFields.has(field))
    && ['quotationNo', 'supplierId', 'inquiryNo', 'quotationStatus', 'items', 'price', 'currency', 'deliveryDays'].every((field) => quotationFields.has(field))
    && [SUPPLIER_INQUIRY_TASK_RUNTIME_MAPPING, SUPPLIER_QUOTATION_RUNTIME_MAPPING].every((item) => item.source === 'server_facts')
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
