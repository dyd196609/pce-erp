export const PURCHASE_ORDER_LINE_DOMAIN_MODEL_VERSION = 'V1.14.2.8.5.6'

const field = (name, type, required = true) => Object.freeze({ name, type, required })

export const PURCHASE_ORDER_LINE_DOMAIN_MODEL = Object.freeze({
  objectCode: 'SCM_PURCHASE_ORDER_LINE',
  objectName: '采购订单明细领域定义',
  businessObject: 'PurchaseOrderLineDomain',
  fields: Object.freeze([
    field('sourceLineReferenceId', 'object_reference'),
    field('materialId', 'object_reference'),
    field('quantity', 'quantity'),
    field('unit', 'string'),
    field('orderAmountReference', 'money_reference'),
    field('deliveryRequirement', 'object'),
  ]),
  parentObject: 'SCM_PURCHASE_ORDER',
  relationshipType: 'composition_definition',
  independentCreationAllowed: false,
  persistenceMode: 'definition_only',
  createdAutomatically: false,
  automaticCreation: false,
  createsBusinessTransaction: false,
})

export function validatePurchaseOrderLineDomainModel(model = PURCHASE_ORDER_LINE_DOMAIN_MODEL) {
  const requiredFields = ['sourceLineReferenceId', 'materialId', 'quantity', 'unit', 'orderAmountReference', 'deliveryRequirement']
  const fields = new Set(model?.fields?.map(item => item.name) || [])
  const missing = requiredFields.filter(name => !fields.has(name))
  if (model?.parentObject !== 'SCM_PURCHASE_ORDER') missing.push('parentObject')
  if (model?.independentCreationAllowed !== false) missing.push('independentCreationAllowed')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', missing: Object.freeze(missing) })
}
