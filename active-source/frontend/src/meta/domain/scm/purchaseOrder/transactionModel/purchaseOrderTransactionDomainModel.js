export const PURCHASE_ORDER_TRANSACTION_DOMAIN_VERSION = 'V1.14.2.8.5.9'
export const PURCHASE_ORDER_TRANSACTION_OBJECT_CODE = 'SCM_PURCHASE_ORDER_TRANSACTION'

const field = (name, type) => Object.freeze({ name, type, required: true })

export const PURCHASE_ORDER_TRANSACTION_DOMAIN_MODEL = Object.freeze({
  objectCode: PURCHASE_ORDER_TRANSACTION_OBJECT_CODE,
  objectName: 'Purchase Order Transaction',
  businessObject: 'PurchaseOrderTransaction',
  fields: Object.freeze([
    field('transactionNo', 'business_identifier'),
    field('purchaseOrderDomainId', 'object_reference'),
    field('sourceReference', 'object_reference'),
    field('supplierId', 'master_data_reference'),
    field('orderLines', 'aggregate_reference'),
    field('totalAmountReference', 'fact_reference'),
    field('currency', 'currency_code'),
    field('lifecycleStatus', 'status'),
    field('approvalReference', 'object_reference'),
  ]),
  persistenceMode: 'definition_only',
  createdAutomatically: false,
  automaticCreation: false,
  createsBusinessTransaction: false,
  executesTransaction: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validatePurchaseOrderTransactionDomainModel(model = PURCHASE_ORDER_TRANSACTION_DOMAIN_MODEL) {
  const requiredFields = ['transactionNo', 'purchaseOrderDomainId', 'sourceReference', 'supplierId', 'orderLines', 'totalAmountReference', 'currency', 'lifecycleStatus', 'approvalReference']
  const fields = new Set(model?.fields?.map(item => item.name) || [])
  const missing = requiredFields.filter(name => !fields.has(name))
  for (const flag of ['createdAutomatically', 'createsBusinessTransaction', 'executesTransaction']) {
    if (model?.[flag] !== false) missing.push(flag)
  }
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', valid: missing.length === 0, missing: Object.freeze(missing) })
}

export function buildPurchaseOrderTransactionDefinition(input = {}) {
  const requiredFields = PURCHASE_ORDER_TRANSACTION_DOMAIN_MODEL.fields.map(item => item.name)
  const missingFields = Object.freeze(requiredFields.filter(name => {
    const value = input[name]
    return name === 'orderLines' ? !Array.isArray(value) || value.length === 0 : value === undefined || value === null || value === ''
  }))
  return Object.freeze({
    definitionStatus: missingFields.length ? 'blocked' : 'ready',
    ...Object.fromEntries(requiredFields.map(name => [name, name === 'orderLines' ? Object.freeze(Array.isArray(input[name]) ? [...input[name]] : []) : input[name] ?? null])),
    missingFields,
    createdAutomatically: false,
    createsBusinessTransaction: false,
    executesTransaction: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
