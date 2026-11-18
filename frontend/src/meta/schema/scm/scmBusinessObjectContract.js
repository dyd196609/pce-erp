export const SCM_BUSINESS_OBJECT_CONTRACT_VERSION = 'V1.14.2.8.4.13'

export const SCM_BUSINESS_OBJECT_FIELDS = Object.freeze([
  'objectId',
  'objectType',
  'objectNo',
  'sourceObjectId',
  'sourceObjectType',
  'status',
  'items',
  'quantity',
  'amount',
  'createdAt',
])

const definitions = [
  ['PurchaseRequest', null, 'PurchaseInquiry', ['draft', 'submitted', 'approved', 'converted', 'closed']],
  ['PurchaseInquiry', 'PurchaseRequest', 'PriceApproval', ['draft', 'sent', 'quoted', 'approved', 'closed']],
  ['PriceApproval', 'PurchaseInquiry', 'PurchaseOrder', ['draft', 'reviewing', 'approved', 'rejected']],
  ['PurchaseOrder', 'PriceApproval', 'PurchaseReceipt', ['draft', 'approved', 'issued', 'completed', 'closed']],
  ['PurchaseReceipt', 'PurchaseOrder', 'PurchaseInspection', ['draft', 'receiving', 'received', 'closed']],
  ['PurchaseInspection', 'PurchaseReceipt', 'WarehouseInbound', ['pending', 'inspecting', 'qualified', 'rejected']],
  ['WarehouseInbound', 'PurchaseInspection', null, ['planned', 'processing', 'completed', 'closed']],
].map(([objectType, sourceObjectType, targetObjectType, statuses]) => Object.freeze({
  objectType,
  sourceObjectType,
  targetObjectType,
  fields: SCM_BUSINESS_OBJECT_FIELDS,
  statuses: Object.freeze(statuses),
  persistence: 'server',
  automaticCreation: false,
  historicalBackfill: false,
}))

export const SCM_BUSINESS_OBJECT_CONTRACTS = Object.freeze(definitions)

export const PURCHASE_ORDER_CREATION_POLICY = Object.freeze({
  requiredSourceObjectType: 'PriceApproval',
  requiredSourceStatus: 'approved',
  quantityRule: 'quantity > 0',
  requiresUserConfirmation: true,
  automaticCreation: false,
})

export function findScmBusinessObjectContract(objectType) {
  const contract = definitions.find((item) => item.objectType === objectType)
  return contract ? { ...contract } : null
}

export function validateScmBusinessObjectShape(value = {}) {
  const missingFields = SCM_BUSINESS_OBJECT_FIELDS.filter((field) => !(field in value))
  return { result: missingFields.length ? 'FAIL' : 'PASS', missingFields }
}
