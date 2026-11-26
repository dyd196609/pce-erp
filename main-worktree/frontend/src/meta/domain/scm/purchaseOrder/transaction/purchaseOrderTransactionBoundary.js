export const PURCHASE_ORDER_TRANSACTION_BOUNDARY_VERSION = 'V1.14.2.8.5.7'

const field = (name, type) => Object.freeze({ name, type, required: true })

export const PURCHASE_ORDER_TRANSACTION_BOUNDARY = Object.freeze({
  objectCode: 'SCM_PURCHASE_ORDER_TRANSACTION_BOUNDARY',
  objectName: '采购订单事务边界',
  businessObject: 'PurchaseOrderTransactionBoundary',
  fields: Object.freeze([
    field('purchaseOrderDomainId', 'object_reference'),
    field('creationGateId', 'object_reference'),
    field('boundaryStatus', 'status'),
    field('transactionAllowed', 'boolean'),
    field('blockingReasons', 'array'),
    field('evidenceReferences', 'array_reference'),
  ]),
  persistenceMode: 'definition_only',
  createdAutomatically: false,
  automaticCreation: false,
  createsPurchaseOrder: false,
  executesTransaction: false,
})

export function validatePurchaseOrderTransactionBoundary(model = PURCHASE_ORDER_TRANSACTION_BOUNDARY) {
  const requiredFields = ['purchaseOrderDomainId', 'creationGateId', 'boundaryStatus', 'transactionAllowed', 'blockingReasons', 'evidenceReferences']
  const fields = new Set(model?.fields?.map(item => item.name) || [])
  const missing = requiredFields.filter(name => !fields.has(name))
  if (model?.createdAutomatically !== false) missing.push('createdAutomatically')
  if (model?.createsPurchaseOrder !== false) missing.push('createsPurchaseOrder')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', missing: Object.freeze(missing) })
}
