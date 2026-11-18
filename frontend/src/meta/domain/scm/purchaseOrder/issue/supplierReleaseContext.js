export const SUPPLIER_RELEASE_CONTEXT_VERSION = 'V1.14.2.8.5.10'
export const SUPPLIER_RELEASE_CONTEXT_CODE = 'SCM_SUPPLIER_RELEASE_CONTEXT'

const field = (name, type) => Object.freeze({ name, type, required: true })

export const SUPPLIER_RELEASE_CONTEXT = Object.freeze({
  objectCode: SUPPLIER_RELEASE_CONTEXT_CODE,
  objectName: 'Supplier Release Context',
  businessObject: 'SupplierReleaseContext',
  fields: Object.freeze([
    field('supplierId', 'master_data_reference'),
    field('supplierContactReference', 'object_reference'),
    field('orderSummaryReference', 'fact_reference'),
    field('deliveryRequirement', 'fact_reference'),
    field('releaseEvidence', 'evidence_reference'),
  ]),
  persistenceMode: 'definition_only',
  createdAutomatically: false,
  supplierApiCallAllowed: false,
  callsSupplierApi: false,
  sendsSupplier: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function buildSupplierReleaseContext(input = {}) {
  const requiredFields = SUPPLIER_RELEASE_CONTEXT.fields.map(item => item.name)
  const missingFields = Object.freeze(requiredFields.filter(name => input[name] === undefined || input[name] === null || input[name] === ''))
  return Object.freeze({
    contextStatus: missingFields.length ? 'blocked' : 'ready',
    ...Object.fromEntries(requiredFields.map(name => [name, input[name] ?? null])),
    missingFields,
    supplierApiCallAllowed: false,
    callsSupplierApi: false,
    sendsSupplier: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export function validateSupplierReleaseContext(model = SUPPLIER_RELEASE_CONTEXT) {
  const requiredFields = ['supplierId', 'supplierContactReference', 'orderSummaryReference', 'deliveryRequirement', 'releaseEvidence']
  const fields = new Set(model?.fields?.map(item => item.name) || [])
  const missing = requiredFields.filter(name => !fields.has(name))
  if (model?.supplierApiCallAllowed !== false) missing.push('supplierApiCallAllowed')
  if (model?.callsSupplierApi !== false) missing.push('callsSupplierApi')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', valid: missing.length === 0, missing: Object.freeze(missing) })
}
