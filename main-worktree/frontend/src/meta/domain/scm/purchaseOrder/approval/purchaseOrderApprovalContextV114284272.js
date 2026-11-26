export const PURCHASE_ORDER_APPROVAL_CONTEXT_VERSION_V114284272 = 'V1.14.2.8.4.27.2'
export const PURCHASE_ORDER_APPROVAL_CONTEXT_CODE_V114284272 =
  'SCM_PURCHASE_ORDER_APPROVAL_CONTEXT_V114284272'

const freeze = value => Object.freeze(value)
const text = value => String(value ?? '').trim()
const clone = value => JSON.parse(JSON.stringify(value))

const requiredFields = freeze([
  'purchaseOrderId',
  'purchaseOrderNo',
  'supplierId',
  'sourceGateId',
  'sourcePurchaseRequestIds',
  'approvalStatus',
  'approvalHistory',
])

export const PURCHASE_ORDER_APPROVAL_STATUSES_V114284272 = freeze([
  'not_started', 'pending_approval', 'approved', 'rejected', 'cancelled',
])

export const PURCHASE_ORDER_APPROVAL_CONTEXT_V114284272 = freeze({
  objectCode: PURCHASE_ORDER_APPROVAL_CONTEXT_CODE_V114284272,
  businessObject: 'PurchaseOrderApprovalContext',
  objectIdField: 'approvalContextId',
  businessNoField: 'purchaseOrderNo',
  sourceRelationsField: 'sourcePurchaseRequestIds',
  fields: freeze([
    'approvalContextId', ...requiredFields,
  ]),
  persistenceMode: 'governed_context_projection',
  createsApprovalInstance: false,
  submitsApproval: false,
  approvesPurchaseOrder: false,
  automaticApproval: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function buildPurchaseOrderApprovalContextV114284272(input = {}) {
  const purchaseOrderId = text(input.purchaseOrderId)
  const sourcePurchaseRequestIds = freeze([...new Set(
    (Array.isArray(input.sourcePurchaseRequestIds) ? input.sourcePurchaseRequestIds : [])
      .map(text).filter(Boolean),
  )])
  const approvalHistory = freeze(clone(
    Array.isArray(input.approvalHistory) ? input.approvalHistory : [],
  ).map(item => freeze(item)))
  const context = {
    objectType: 'PurchaseOrderApprovalContext',
    approvalContextId: text(input.approvalContextId)
      || (purchaseOrderId ? `POAC-${purchaseOrderId}` : ''),
    purchaseOrderId,
    purchaseOrderNo: text(input.purchaseOrderNo),
    supplierId: text(input.supplierId),
    sourceGateId: text(input.sourceGateId),
    sourcePurchaseRequestIds,
    approvalStatus: text(input.approvalStatus) || 'not_started',
    approvalHistory,
    automaticApproval: false,
    approvalSubmitted: false,
    purchaseOrderStatusChanged: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  }
  const validation = validatePurchaseOrderApprovalContextV114284272(context)
  return freeze({ ...context,
    contextStatus: validation.result === 'PASS' ? 'ready' : 'blocked',
    validation,
  })
}

export function validatePurchaseOrderApprovalContextV114284272(context = {}) {
  const missingFields = []
  for (const field of ['approvalContextId', 'purchaseOrderId', 'purchaseOrderNo',
    'supplierId', 'sourceGateId']) {
    if (!text(context[field])) missingFields.push(field)
  }
  if (!Array.isArray(context.sourcePurchaseRequestIds)) missingFields.push('sourcePurchaseRequestIds')
  if (!Array.isArray(context.approvalHistory)) missingFields.push('approvalHistory')
  if (!PURCHASE_ORDER_APPROVAL_STATUSES_V114284272.includes(context.approvalStatus)) {
    missingFields.push('approvalStatus')
  }
  const invalidHistoryIndexes = Array.isArray(context.approvalHistory)
    ? context.approvalHistory.map((item, index) => ({ item, index }))
      .filter(({ item }) => !text(item?.recordId) || !text(item?.result)
        || !text(item?.approvedBy) || !text(item?.approvedAt))
      .map(({ index }) => index) : []
  if (invalidHistoryIndexes.length) missingFields.push('approvalHistoryRecord')
  return freeze({
    result: missingFields.length ? 'FAIL' : 'PASS',
    valid: missingFields.length === 0,
    missingFields: freeze(missingFields),
    invalidHistoryIndexes: freeze(invalidHistoryIndexes),
    sourceRelationCount: Array.isArray(context.sourcePurchaseRequestIds)
      ? context.sourcePurchaseRequestIds.length : 0,
  })
}
