export const PURCHASE_ORDER_TRANSACTION_LINE_VERSION = 'V1.14.2.8.5.9'
export const PURCHASE_ORDER_TRANSACTION_LINE_OBJECT_CODE = 'SCM_PURCHASE_ORDER_TRANSACTION_LINE'

const field = (name, type) => Object.freeze({ name, type, required: true })

export const PURCHASE_ORDER_TRANSACTION_LINE_DOMAIN_MODEL = Object.freeze({
  objectCode: PURCHASE_ORDER_TRANSACTION_LINE_OBJECT_CODE,
  objectName: 'Purchase Order Transaction Line',
  businessObject: 'PurchaseOrderTransactionLine',
  fields: Object.freeze([
    field('lineNo', 'line_identifier'),
    field('transactionId', 'parent_reference'),
    field('itemReference', 'master_data_reference'),
    field('quantityReference', 'fact_reference'),
    field('unitPriceReference', 'fact_reference'),
    field('amountReference', 'fact_reference'),
    field('deliveryRequirement', 'fact_reference'),
  ]),
  persistenceMode: 'definition_only',
  createdAutomatically: false,
  automaticCreation: false,
  independentCreationAllowed: false,
  createsBusinessTransaction: false,
  executesTransaction: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validatePurchaseOrderTransactionLineDomainModel(model = PURCHASE_ORDER_TRANSACTION_LINE_DOMAIN_MODEL) {
  const requiredFields = ['lineNo', 'transactionId', 'itemReference', 'quantityReference', 'unitPriceReference', 'amountReference', 'deliveryRequirement']
  const fields = new Set(model?.fields?.map(item => item.name) || [])
  const missing = requiredFields.filter(name => !fields.has(name))
  if (model?.independentCreationAllowed !== false) missing.push('independentCreationAllowed')
  if (model?.createsBusinessTransaction !== false) missing.push('createsBusinessTransaction')
  if (model?.executesTransaction !== false) missing.push('executesTransaction')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', valid: missing.length === 0, missing: Object.freeze(missing) })
}
