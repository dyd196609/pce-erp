const READONLY_STATUSES = ['submitted', 'reviewing', 'reviewed', 'rechecking', 'rechecked', 'approved', 'converted', 'issued', 'receiving', 'received', 'closed', 'cancelled', 'fullyReceived']
const RECEIVABLE_PURCHASE_ORDER_STATUSES = ['approved', 'converted', 'issued', 'released', 'ordered', 'partiallyReceived']
const BLOCKED_RECEIVE_STATUSES = ['draft', 'submitted', 'reviewing', 'cancelled', 'closed', 'fullyReceived']

const STATUS_LABELS = {
  draft: '草稿',
  submitted: '待审核',
  reviewing: '审核中',
  reviewed: '待复核',
  rechecking: '复核中',
  rechecked: '待审批',
  approved: '已审批',
  converted: '已转单',
  issued: '已下达',
  released: '已释放',
  ordered: '已订购',
  partiallyReceived: '部分收货',
  receiving: '收货中',
  received: '已收货',
  fullyReceived: '完全收货',
  closed: '已关闭',
  cancelled: '已取消',
  sent: '已发送',
  quoted: '已报价',
  rejected: '已驳回',
}

function configuredApprovalCount(moduleName) {
  try {
    const raw = localStorage.getItem('approval-flow-config-state-v1')
    if (!raw) return moduleName === 'purchaseInquiry' ? 2 : 3
    const state = JSON.parse(raw)
    const config = (state.approvalFlowConfigs || []).find((item) => item.moduleName === moduleName)
    return config?.enabled === false ? 1 : Math.max(1, config?.steps?.length || (moduleName === 'purchaseInquiry' ? 2 : 3))
  } catch {
    return moduleName === 'purchaseInquiry' ? 2 : 3
  }
}

function baseRule(status = 'draft') {
  const readonly = READONLY_STATUSES.includes(status)
  return {
    editHeader: !readonly || status === 'draft',
    editLines: !readonly,
    addLine: !readonly,
    deleteLine: !readonly,
    submit: status === 'draft' || status === 'rejected',
    approve: ['submitted', 'reviewed', 'rechecked'].includes(status),
    convert: status === 'approved',
    issue: false,
    sendToWms: false,
    void: !['closed', 'cancelled', 'fullyReceived'].includes(status),
  }
}

export function getScmDocumentRule(moduleName, status = 'draft') {
  const rule = baseRule(status)
  if (['purchaseInquiry', 'priceApproval', 'purchaseOrder'].includes(moduleName)) {
    rule.addLine = false
    rule.deleteLine = false
    rule.editLines = status !== 'issued' && !['closed', 'cancelled', 'fullyReceived'].includes(status)
  }
  if (moduleName === 'purchaseInquiry') {
    rule.submit = status === 'draft' || status === 'rejected'
    rule.approve = ['submitted', 'reviewed', 'rechecked', 'sent', 'quoted'].includes(status)
    rule.convert = ['approved', 'quoted'].includes(status)
  }
  if (moduleName === 'purchaseOrder') {
    rule.issue = status === 'approved'
    rule.sendToWms = RECEIVABLE_PURCHASE_ORDER_STATUSES.includes(status)
    if (status === 'issued') {
      rule.editHeader = false
      rule.addLine = false
      rule.editLines = false
      rule.deleteLine = false
    }
  }
  if (status === 'converted') rule.convert = false
  if (['closed', 'cancelled', 'fullyReceived'].includes(status)) {
    Object.assign(rule, { editHeader: false, editLines: false, addLine: false, deleteLine: false, submit: false, approve: false, convert: false, issue: false, sendToWms: false, void: false })
  }
  return rule
}

export function canEditHeader(moduleName, status) { return getScmDocumentRule(moduleName, status).editHeader }
export function canEditLines(moduleName, status) { return getScmDocumentRule(moduleName, status).editLines }
export function canAddLine(moduleName, status) { return getScmDocumentRule(moduleName, status).addLine }
export function canDeleteLine(moduleName, status) { return getScmDocumentRule(moduleName, status).deleteLine }
export function canSubmit(moduleName, status) { return getScmDocumentRule(moduleName, status).submit }
export function canApprove(moduleName, status) { return getScmDocumentRule(moduleName, status).approve }
export function canConvert(moduleName, status) { return getScmDocumentRule(moduleName, status).convert }
export function canIssuePurchaseOrder(status) { return getScmDocumentRule('purchaseOrder', status).issue }
export function canSendToWms(status) { return getScmDocumentRule('purchaseOrder', status).sendToWms }

export function isReceivablePurchaseOrderStatus(status) {
  return RECEIVABLE_PURCHASE_ORDER_STATUSES.includes(status) && !BLOCKED_RECEIVE_STATUSES.includes(status)
}

export function getReadonlyReason(moduleName, status = 'draft') {
  if (!READONLY_STATUSES.includes(status)) return ''
  const moduleLabel = {
    purchaseRequest: '采购申请',
    purchaseInquiry: '采购询价',
    priceApproval: '核价单',
    purchaseApproval: '采购审批',
    purchaseOrder: '采购订单',
  }[moduleName] || '当前单据'
  const statusLabel = STATUS_LABELS[status] || status
  if (moduleName === 'purchaseRequest' && status === 'submitted') return '采购申请已提报，不能修改业务明细；如需修改，请撤回或作废后重新创建。'
  if (status === 'issued') return `${moduleLabel}已下达，不能新增、编辑或删除物料明细，可进入 WMS 收货预备。`
  if (['purchaseInquiry', 'priceApproval', 'purchaseOrder'].includes(moduleName)) return '该单据来源于上一流程，不能新增或删除来源物料明细。'
  if (['closed', 'cancelled', 'fullyReceived'].includes(status)) return `${moduleLabel}${statusLabel}，全部只读。`
  return `${moduleLabel}${statusLabel}，不能修改业务明细；如需修改，请撤回或作废后重新创建。`
}

export function getStatusLabel(status) {
  return STATUS_LABELS[status] || status || '草稿'
}

export function getStatusDisplayLabel(moduleName, status = 'draft') {
  if (status === 'submitted' && configuredApprovalCount(moduleName) === 1) return '待审批'
  if (status === 'reviewed' && configuredApprovalCount(moduleName) === 2) return '待审批'
  return getStatusLabel(status)
}

export function getNextApprovalAction(moduleName, status = 'draft') {
  const count = configuredApprovalCount(moduleName)
  if (status === 'draft' || status === 'rejected') return 'submit'
  if (status === 'submitted') return count === 1 ? 'approve' : 'review'
  if (status === 'reviewed') return count === 2 ? 'approve' : 'recheck'
  if (status === 'rechecked') return 'approve'
  return ''
}

export function getNextApprovalButtonLabel(moduleName, status = 'draft') {
  return {
    submit: '提报',
    review: '审核',
    recheck: '复核',
    approve: '审批',
  }[getNextApprovalAction(moduleName, status)] || ''
}

export function getNextBusinessAction(moduleName, status = 'draft') {
  if (status === 'approved') {
    return {
      purchaseRequest: '生成询价单',
      purchaseInquiry: '生成核价单',
      priceApproval: '生成采购订单',
      purchaseOrder: '下达采购订单',
    }[moduleName] || ''
  }
  if (['completed', 'quoted'].includes(status) && moduleName === 'purchaseInquiry') return '生成核价单'
  if (status === 'issued' && moduleName === 'purchaseOrder') return '进入 WMS 收货预备'
  return ''
}
