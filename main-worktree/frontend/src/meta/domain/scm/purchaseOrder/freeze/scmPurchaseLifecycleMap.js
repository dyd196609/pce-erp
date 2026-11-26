export const SCM_PURCHASE_LIFECYCLE_MAP_VERSION = 'V1.14.2.8.5.11'
export const SCM_PURCHASE_LIFECYCLE_MAP_CODE = 'SCM_PURCHASE_LIFECYCLE_MAP'

const node = (sequence, nodeCode, name, version, objectCode, acceptanceProfileCode) => Object.freeze({
  sequence,
  nodeCode,
  name,
  version,
  objectCode,
  acceptanceProfileCode,
  persistenceMode: 'definition_only',
  executionAllowed: false,
})

export const SCM_PURCHASE_LIFECYCLE_NODES = Object.freeze([
  node(1, 'PURCHASE_INQUIRY', 'Purchase Inquiry', 'V1.14.2.8.5.1', 'SCM_PURCHASE_INQUIRY', 'SCM_PURCHASE_INQUIRY_ACCEPTANCE_PROFILE'),
  node(2, 'SUPPLIER_QUOTE', 'Supplier Quote', 'V1.14.2.8.5.3', 'SCM_SUPPLIER_QUOTE', 'SCM_SUPPLIER_QUOTE_ACCEPTANCE_PROFILE'),
  node(3, 'QUOTE_COMPARISON', 'Quote Comparison', 'V1.14.2.8.5.3', 'SCM_QUOTE_COMPARISON', 'SCM_QUOTE_COMPARISON_ACCEPTANCE_PROFILE'),
  node(4, 'SUPPLIER_RECOMMENDATION_DECISION', 'Supplier Recommendation Decision', 'V1.14.2.8.5.4', 'SCM_SUPPLIER_RECOMMENDATION_DECISION', 'SCM_SUPPLIER_RECOMMENDATION_DECISION_ACCEPTANCE_PROFILE'),
  node(5, 'PURCHASE_ORDER_CREATION_GATE', 'Purchase Order Creation Gate', 'V1.14.2.8.5.5', 'SCM_PURCHASE_ORDER_CREATION_GATE', 'SCM_PURCHASE_ORDER_CREATION_GATE_ACCEPTANCE_PROFILE'),
  node(6, 'PURCHASE_ORDER_DOMAIN', 'Purchase Order Domain', 'V1.14.2.8.5.6', 'SCM_PURCHASE_ORDER', 'SCM_PURCHASE_ORDER_DOMAIN_ACCEPTANCE_PROFILE'),
  node(7, 'PURCHASE_ORDER_TRANSACTION_BOUNDARY', 'Purchase Order Transaction Boundary', 'V1.14.2.8.5.7', 'SCM_PURCHASE_ORDER_TRANSACTION_BOUNDARY', 'SCM_PURCHASE_ORDER_TRANSACTION_BOUNDARY_ACCEPTANCE_PROFILE'),
  node(8, 'PURCHASE_ORDER_APPROVAL_INTERFACE', 'Purchase Order Approval Interface', 'V1.14.2.8.5.8', 'SCM_PURCHASE_ORDER_APPROVAL_INTERFACE_BOUNDARY', 'SCM_PURCHASE_ORDER_APPROVAL_INTERFACE_ACCEPTANCE_PROFILE'),
  node(9, 'PURCHASE_ORDER_TRANSACTION', 'Purchase Order Transaction', 'V1.14.2.8.5.9', 'SCM_PURCHASE_ORDER_TRANSACTION', 'SCM_PURCHASE_ORDER_TRANSACTION_ACCEPTANCE_PROFILE'),
  node(10, 'PURCHASE_ORDER_LIFECYCLE', 'Purchase Order Lifecycle', 'V1.14.2.8.5.9', 'SCM_PURCHASE_ORDER_LIFECYCLE_STATE', 'SCM_PURCHASE_ORDER_TRANSACTION_ACCEPTANCE_PROFILE'),
  node(11, 'PURCHASE_ORDER_ISSUE_BOUNDARY', 'Purchase Order Issue Boundary', 'V1.14.2.8.5.10', 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY', 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_ACCEPTANCE_PROFILE'),
])

export const SCM_PURCHASE_LIFECYCLE_MAP = Object.freeze({
  mapCode: SCM_PURCHASE_LIFECYCLE_MAP_CODE,
  nodes: SCM_PURCHASE_LIFECYCLE_NODES,
  firstFrozenVersion: 'V1.14.2.8.5.3',
  lastFrozenVersion: 'V1.14.2.8.5.10',
  mode: 'read_only',
  frozen: true,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateScmPurchaseLifecycleMap(map = SCM_PURCHASE_LIFECYCLE_MAP) {
  const missing = []
  if (map?.nodes?.length !== 11) missing.push('nodes')
  if (!map?.nodes?.every((item, index) => item.sequence === index + 1 && item.objectCode && item.acceptanceProfileCode && item.executionAllowed === false)) missing.push('nodeContract')
  if (map?.mode !== 'read_only') missing.push('mode')
  if (map?.frozen !== true) missing.push('frozen')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', valid: missing.length === 0, missing: Object.freeze(missing) })
}
