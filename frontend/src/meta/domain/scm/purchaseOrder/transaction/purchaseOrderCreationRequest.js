export const PURCHASE_ORDER_CREATION_REQUEST_VERSION = 'V1.14.2.8.5.7'

const field = (name, type) => Object.freeze({ name, type, required: true })

export const PURCHASE_ORDER_CREATION_REQUEST = Object.freeze({
  objectCode: 'SCM_PURCHASE_ORDER_CREATION_REQUEST',
  objectName: '采购订单创建请求',
  businessObject: 'PurchaseOrderCreationRequest',
  fields: Object.freeze([
    field('transactionBoundaryId', 'object_reference'),
    field('purchaseOrderDomainId', 'object_reference'),
    field('requester', 'actor_reference'),
    field('requestReason', 'string'),
    field('riskStatus', 'status'),
    field('requestStatus', 'status'),
  ]),
  persistenceMode: 'definition_only',
  createdAutomatically: false,
  automaticCreation: false,
  submitsWorkflow: false,
  createsPurchaseOrder: false,
})

export function validatePurchaseOrderCreationRequest(model = PURCHASE_ORDER_CREATION_REQUEST) {
  const requiredFields = ['requester', 'requestReason', 'riskStatus', 'requestStatus']
  const fields = new Set(model?.fields?.map(item => item.name) || [])
  const missing = requiredFields.filter(name => !fields.has(name))
  if (model?.submitsWorkflow !== false) missing.push('submitsWorkflow')
  if (model?.createsPurchaseOrder !== false) missing.push('createsPurchaseOrder')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', missing: Object.freeze(missing) })
}
