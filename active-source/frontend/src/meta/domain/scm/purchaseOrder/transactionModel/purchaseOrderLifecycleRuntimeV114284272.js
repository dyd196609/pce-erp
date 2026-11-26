import { PURCHASE_ORDER_LIFECYCLE_STATES } from './purchaseOrderLifecycleStateDefinition.js'

export const PURCHASE_ORDER_LIFECYCLE_RUNTIME_VERSION_V114284272 = 'V1.14.2.8.4.27.2'
export const PURCHASE_ORDER_LIFECYCLE_RUNTIME_CODE_V114284272 =
  'SCM_PURCHASE_ORDER_LIFECYCLE_RUNTIME_V114284272'

const freeze = value => Object.freeze(value)
const text = value => String(value ?? '').trim()

export const PURCHASE_ORDER_LIFECYCLE_LABELS_V114284272 = freeze({
  draft: '草稿',
  pending_approval: '待审批',
  approved: '已审批',
  issued: '已下达',
  partially_received: '部分收货',
  completed: '完成',
  cancelled: '取消',
})

export const PURCHASE_ORDER_LIFECYCLE_TRANSITIONS_V114284272 = freeze({
  draft: freeze(['pending_approval', 'cancelled']),
  pending_approval: freeze(['approved', 'cancelled']),
  approved: freeze(['issued', 'cancelled']),
  issued: freeze(['partially_received', 'cancelled']),
  partially_received: freeze(['completed', 'cancelled']),
  completed: freeze([]),
  cancelled: freeze([]),
})

function blocked(reason, currentStatus = null, targetStatus = null) {
  return freeze({
    result: 'FAIL',
    transitionAllowed: false,
    reason,
    currentStatus,
    targetStatus,
    projectedStatus: currentStatus,
    stateTransitionExecuted: false,
    automaticTransition: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

function matchingApprovalContext(purchaseOrder, approvalContext) {
  return text(approvalContext?.purchaseOrderId) === text(purchaseOrder?.id)
    && text(approvalContext?.purchaseOrderNo) === text(purchaseOrder?.poNo)
    && text(approvalContext?.supplierId) === text(purchaseOrder?.supplierId)
    && text(approvalContext?.sourceGateId) === text(purchaseOrder?.sourceGateId)
}

function approvalHistoryConfirms(approvalContext) {
  const history = Array.isArray(approvalContext?.approvalHistory)
    ? approvalContext.approvalHistory : []
  return history.some(item => item?.result === 'approved'
    && text(item?.approvedBy) && text(item?.approvedAt))
}

export function evaluatePurchaseOrderLifecycleTransitionV114284272({
  purchaseOrder = {},
  targetStatus = '',
  actor = '',
  reason = '',
  approvalContext = null,
  issueConfirmation = null,
  receiptEvidence = null,
  automatic = false,
} = {}) {
  const currentStatus = text(purchaseOrder.lifecycleStatus || purchaseOrder.status)
  const target = text(targetStatus)
  if (purchaseOrder.objectType !== 'PurchaseOrder' || !text(purchaseOrder.id)
    || !text(purchaseOrder.poNo)) {
    return blocked('PURCHASE_ORDER_IDENTITY_INCOMPLETE', currentStatus, target)
  }
  if (purchaseOrder.classification !== 'GATE_CREATED') {
    return blocked('LEGACY_PURCHASE_ORDER_LIFECYCLE_ISOLATED', currentStatus, target)
  }
  if (!PURCHASE_ORDER_LIFECYCLE_STATES.includes(currentStatus)
    || !PURCHASE_ORDER_LIFECYCLE_STATES.includes(target)) {
    return blocked('PURCHASE_ORDER_LIFECYCLE_STATUS_UNKNOWN', currentStatus, target)
  }
  if (automatic === true || !text(actor)) {
    return blocked('EXPLICIT_HUMAN_LIFECYCLE_ACTION_REQUIRED', currentStatus, target)
  }
  if (!PURCHASE_ORDER_LIFECYCLE_TRANSITIONS_V114284272[currentStatus]?.includes(target)) {
    return blocked('PURCHASE_ORDER_LIFECYCLE_CROSS_STATE_TRANSITION_FORBIDDEN',
      currentStatus, target)
  }
  if (target === 'cancelled' && !text(reason)) {
    return blocked('PURCHASE_ORDER_CANCELLATION_REASON_REQUIRED', currentStatus, target)
  }
  if (target === 'pending_approval'
    && (!matchingApprovalContext(purchaseOrder, approvalContext)
      || approvalContext?.approvalStatus !== 'pending_approval')) {
    return blocked('PURCHASE_ORDER_APPROVAL_CONTEXT_NOT_READY', currentStatus, target)
  }
  if (target === 'approved'
    && (!matchingApprovalContext(purchaseOrder, approvalContext)
      || approvalContext?.approvalStatus !== 'approved'
      || !approvalHistoryConfirms(approvalContext))) {
    return blocked('PURCHASE_ORDER_APPROVAL_RESULT_NOT_CONFIRMED', currentStatus, target)
  }
  if (target === 'issued'
    && (issueConfirmation?.confirmed !== true
      || !text(issueConfirmation?.confirmedBy)
      || !text(issueConfirmation?.confirmedAt))) {
    return blocked('PURCHASE_ORDER_MANUAL_ISSUE_CONFIRMATION_REQUIRED', currentStatus, target)
  }
  if (target === 'partially_received'
    && (receiptEvidence?.confirmed !== true
      || !text(receiptEvidence?.confirmedBy)
      || !text(receiptEvidence?.confirmedAt))) {
    return blocked('PURCHASE_ORDER_MANUAL_RECEIPT_EVIDENCE_REQUIRED', currentStatus, target)
  }
  if (target === 'completed'
    && (receiptEvidence?.completed !== true
      || !text(receiptEvidence?.confirmedBy)
      || !text(receiptEvidence?.confirmedAt))) {
    return blocked('PURCHASE_ORDER_COMPLETION_EVIDENCE_REQUIRED', currentStatus, target)
  }
  return freeze({
    result: 'PASS',
    transitionAllowed: true,
    reason: '',
    currentStatus,
    currentStatusLabel: PURCHASE_ORDER_LIFECYCLE_LABELS_V114284272[currentStatus],
    targetStatus: target,
    targetStatusLabel: PURCHASE_ORDER_LIFECYCLE_LABELS_V114284272[target],
    projectedStatus: target,
    actor: text(actor),
    actionReason: text(reason),
    stateTransitionExecuted: false,
    automaticTransition: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export function buildPurchaseOrderLifecycleSnapshotV114284272(purchaseOrder = {}) {
  const currentStatus = text(purchaseOrder.lifecycleStatus || purchaseOrder.status)
  const currentIndex = PURCHASE_ORDER_LIFECYCLE_STATES.indexOf(currentStatus)
  const mainPath = PURCHASE_ORDER_LIFECYCLE_STATES.filter(status => status !== 'cancelled')
  return freeze({
    runtimeCode: PURCHASE_ORDER_LIFECYCLE_RUNTIME_CODE_V114284272,
    purchaseOrderId: text(purchaseOrder.id),
    purchaseOrderNo: text(purchaseOrder.poNo),
    lifecycleStatus: currentStatus || 'unknown',
    lifecycleStatusLabel: PURCHASE_ORDER_LIFECYCLE_LABELS_V114284272[currentStatus]
      || '状态待确认',
    validStatus: currentIndex >= 0,
    steps: freeze(mainPath.map((status, index) => freeze({
      status,
      label: PURCHASE_ORDER_LIFECYCLE_LABELS_V114284272[status],
      result: currentStatus === 'cancelled' ? 'TERMINATED'
        : index < mainPath.indexOf(currentStatus) ? 'COMPLETED'
          : status === currentStatus ? 'CURRENT' : 'PENDING',
    }))),
    terminalStatus: 'cancelled',
    automaticTransitionAllowed: false,
    stateMutationPerformed: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
