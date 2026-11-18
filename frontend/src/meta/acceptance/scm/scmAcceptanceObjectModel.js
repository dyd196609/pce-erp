export const SCM_ACCEPTANCE_MODEL_VERSION = 'V1.14.2.8.4.23'

const FINANCE_ACTIONS = Object.freeze(['createPayment', 'executePayment', 'bankTransfer', 'postLedger', 'reconcile'])

const defineObject = definition => Object.freeze({
  ...definition,
  lifecycle: Object.freeze([...definition.lifecycle]),
  sourceObjects: Object.freeze([...definition.sourceObjects]),
  targetObjects: Object.freeze([...definition.targetObjects]),
  traceFields: Object.freeze([...definition.traceFields]),
  actionRules: Object.freeze({
    mode: 'whitelist',
    defaultDecision: 'deny',
    financialActionsForbidden: FINANCE_ACTIONS,
  }),
})

export const SCM_ACCEPTANCE_OBJECTS = Object.freeze([
  defineObject({
    objectCode: 'SCM_PURCHASE_REQUEST',
    objectName: '采购申请',
    businessObject: 'PurchaseRequest',
    module: 'SCM',
    lifecycle: ['draft', 'submitted', 'approved', 'released', 'closed'],
    sourceObjects: [],
    targetObjects: ['SCM_PURCHASE_INQUIRY'],
    traceFields: ['sourceObject', 'targetObject', 'relationshipType', 'traceId', 'direction'],
    statusField: 'status',
  }),
  defineObject({
    objectCode: 'SCM_PURCHASE_INQUIRY',
    objectName: '询价',
    businessObject: 'PurchaseInquiry',
    module: 'SCM',
    lifecycle: ['draft', 'issued', 'quoted', 'evaluated', 'closed'],
    sourceObjects: ['SCM_PURCHASE_REQUEST'],
    targetObjects: ['SCM_PRICE_APPROVAL'],
    traceFields: ['sourceObject', 'targetObject', 'relationshipType', 'traceId', 'direction'],
    statusField: 'status',
  }),
  defineObject({
    objectCode: 'SCM_PURCHASE_ORDER',
    objectName: '采购订单',
    businessObject: 'PurchaseOrder',
    module: 'SCM',
    lifecycle: ['draft', 'approved', 'issued', 'received', 'closed'],
    sourceObjects: ['SCM_PRICE_APPROVAL'],
    targetObjects: ['SCM_WAREHOUSE_RECEIPT'],
    traceFields: ['sourceObject', 'targetObject', 'relationshipType', 'traceId', 'direction'],
    statusField: 'status',
  }),
])

const OBJECT_BY_CODE = new Map(SCM_ACCEPTANCE_OBJECTS.map(item => [item.objectCode, item]))
const OBJECT_BY_NAME = new Map(SCM_ACCEPTANCE_OBJECTS.map(item => [item.businessObject, item]))

export function resolveScmAcceptanceObject(objectIdentity = '') {
  return OBJECT_BY_CODE.get(objectIdentity) || OBJECT_BY_NAME.get(objectIdentity) || null
}

export function listScmAcceptanceObjects() {
  return SCM_ACCEPTANCE_OBJECTS
}

