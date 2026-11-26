import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  getPaymentApplicationById,
  linkPaymentApplicationOrderPrepare,
  listPaymentApplications,
} from './paymentApplicationStore.js'

const STORAGE_KEY = 'payment-instruction-prepare-state-v1'
const ACTIVE_STATUSES = ['draft', 'waiting_review', 'reviewed', 'blocked']

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function nowText() {
  return new Date().toISOString()
}

function createId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

function createNo(prefix) {
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)
  return `${prefix}${stamp}${Math.floor(Math.random() * 90 + 10)}`
}

function toNumber(value) {
  const next = Number(value)
  return Number.isFinite(next) ? next : 0
}

function roundAmount(value) {
  return Number(toNumber(value).toFixed(2))
}

function defaultState() {
  return { paymentOrderPrepares: [] }
}

function byId(collection, id) {
  return (collection || []).find((item) => String(item.id) === String(id)) || null
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[PAYMENT INSTRUCTION PREPARE STORE] fallback to empty state', error)
    return defaultState()
  }
}

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function appendLog(current, action, beforeStatus, afterStatus, remark = '', operator = 'page-user') {
  current.logs = [
    ...(current.logs || []),
    {
      action,
      beforeStatus,
      afterStatus,
      operator,
      time: nowText(),
      remark: remark || action,
      sourcePaymentApplicationNo: current.sourcePaymentApplicationNo || '',
      paymentOrderPrepareNo: current.paymentOrderPrepareNo || '',
    },
  ]
}

function paymentOrderPrepare(payload = {}) {
  const stamp = nowText()
  const approvedAmount = roundAmount(payload.approvedAmount)
  const orderAmount = roundAmount(payload.orderAmount ?? approvedAmount)
  return {
    id: payload.id || createId('payment-order-prepare'),
    paymentOrderPrepareNo: payload.paymentOrderPrepareNo || createNo('POP'),
    sourcePaymentApplicationId: payload.sourcePaymentApplicationId || '',
    sourcePaymentApplicationNo: payload.sourcePaymentApplicationNo || '',
    sourcePayableConfirmNo: payload.sourcePayableConfirmNo || '',
    sourceInvoicePrepareNo: payload.sourceInvoicePrepareNo || '',
    sourceSettlementNo: payload.sourceSettlementNo || '',
    supplierId: payload.supplierId || '',
    supplierName: payload.supplierName || '',
    purchaseOrderNo: payload.purchaseOrderNo || '',
    invoiceNo: payload.invoiceNo || '',
    approvedAmount,
    orderAmount,
    currency: payload.currency || 'CNY',
    paymentMethod: payload.paymentMethod || 'bank_transfer',
    plannedPaymentDate: payload.plannedPaymentDate || '',
    paymentPriority: payload.paymentPriority || 'normal',
    paymentPurpose: payload.paymentPurpose || payload.paymentReason || '采购付款申请审批后的付款指令准备',
    payeeName: payload.payeeName || payload.supplierName || '',
    payeeBankName: payload.payeeBankName || '',
    payeeBankAccount: payload.payeeBankAccount || '',
    payerAccountName: payload.payerAccountName || '',
    payerBankName: payload.payerBankName || '',
    payerBankAccount: payload.payerBankAccount || '',
    paymentOrderStatus: payload.paymentOrderStatus || 'draft',
    paymentInstructionStatus: payload.paymentInstructionStatus || 'not_issued',
    paymentExecutionStatus: payload.paymentExecutionStatus || 'not_started',
    paymentVoucherStatus: payload.paymentVoucherStatus || 'not_generated',
    writeOffStatus: payload.writeOffStatus || 'not_written_off',
    ledgerStatus: payload.ledgerStatus || 'not_written_ledger',
    postingStatus: payload.postingStatus || 'not_posted',
    linkedPaymentExecutionPrepareId: payload.linkedPaymentExecutionPrepareId || '',
    linkedPaymentExecutionPrepareNo: payload.linkedPaymentExecutionPrepareNo || '',
    paymentExecutionPrepareGeneratedAt: payload.paymentExecutionPrepareGeneratedAt || '',
    paymentExecutionPrepareGeneratedBy: payload.paymentExecutionPrepareGeneratedBy || '',
    isDemoChain: Boolean(payload.isDemoChain),
    demoChainVersion: payload.demoChainVersion || '',
    demoChainGeneratedAt: payload.demoChainGeneratedAt || '',
    demoChainPurpose: payload.demoChainPurpose || '',
    remark: payload.remark || '',
    createdAt: payload.createdAt || stamp,
    createdBy: payload.createdBy || 'system',
    updatedAt: payload.updatedAt || stamp,
    logs: Array.isArray(payload.logs) ? payload.logs : [],
  }
}

function normalizeState(raw = {}) {
  return { paymentOrderPrepares: (raw.paymentOrderPrepares || []).map(paymentOrderPrepare) }
}

let state = loadState()

export function writePaymentInstructionPrepareLog(action, payload = {}) {
  addOperationLog({
    module: '付款指令准备',
    action,
    targetType: payload.targetType || 'paymentOrderPrepare',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源付款申请：${payload.sourceNo || '-'}`,
      `目标付款指令准备：${payload.targetNo || '-'}`,
      `结果：${payload.result || '成功'}`,
    ].join('；'),
  })
}

export function getPaymentInstructionPrepareState() {
  return clone(state)
}

export function savePaymentInstructionPrepareState(nextState) {
  state = normalizeState(nextState)
  persist()
  writePaymentInstructionPrepareLog('save_payment_order_prepare_state', { targetType: 'paymentOrderPrepareState', targetId: 'state' })
  return getPaymentInstructionPrepareState()
}

export function listPaymentInstructionPrepares() {
  return clone(state.paymentOrderPrepares)
}

export function getPaymentInstructionPrepareById(id) {
  return clone(byId(state.paymentOrderPrepares, id))
}

export function isPaymentOrderPrepareGeneratedFromPaymentApplication(paymentApplicationOrId) {
  const paymentApplication = typeof paymentApplicationOrId === 'object'
    ? paymentApplicationOrId
    : getPaymentApplicationById(paymentApplicationOrId)
  if (!paymentApplication?.id) return false
  if (paymentApplication.linkedPaymentOrderPrepareId || paymentApplication.linkedPaymentOrderPrepareNo) return true
  return state.paymentOrderPrepares.some((item) => (
    String(item.sourcePaymentApplicationId) === String(paymentApplication.id)
    && ACTIVE_STATUSES.includes(item.paymentOrderStatus)
  ))
}

export function getPaymentOrderPrepareCreateGuard(paymentApplication = {}) {
  if (!paymentApplication?.id) return { canCreate: false, reason: '未找到付款申请准备。' }
  if (isPaymentOrderPrepareGeneratedFromPaymentApplication(paymentApplication)) return { canCreate: false, reason: '已存在付款指令准备，不能重复生成。' }
  if (paymentApplication.paymentApplicationStatus !== 'approved') return { canCreate: false, reason: '付款申请准备尚未审批通过。' }
  if (paymentApplication.paymentApprovalStatus !== 'approved') return { canCreate: false, reason: '付款申请审批状态不是已审批。' }
  if (roundAmount(paymentApplication.approvedAmount) <= 0) return { canCreate: false, reason: '批准金额为空或为 0。' }
  if (paymentApplication.paymentExecutionStatus !== 'not_started') return { canCreate: false, reason: '付款执行状态不是未开始。' }
  if (paymentApplication.paymentVoucherStatus !== 'not_generated') return { canCreate: false, reason: '付款凭证状态不是未生成。' }
  if (paymentApplication.writeOffStatus !== 'not_written_off') return { canCreate: false, reason: '核销状态不是未核销。' }
  if (paymentApplication.ledgerStatus !== 'not_written_ledger') return { canCreate: false, reason: '总账状态不是未写总账。' }
  if (paymentApplication.postingStatus !== 'not_posted') return { canCreate: false, reason: '过账状态不是未过账。' }
  if (['blocked', 'closed'].includes(paymentApplication.paymentApplicationStatus)) return { canCreate: false, reason: '付款申请准备已阻断或关闭。' }
  return { canCreate: true, reason: '' }
}

export function getPaymentOrderPrepareSourcesFromPaymentApplications() {
  return listPaymentApplications().map((paymentApplication) => {
    const existed = state.paymentOrderPrepares.find((item) => (
      String(item.sourcePaymentApplicationId) === String(paymentApplication.id)
      && ACTIVE_STATUSES.includes(item.paymentOrderStatus)
    ))
    const generated = isPaymentOrderPrepareGeneratedFromPaymentApplication(paymentApplication)
    const guard = getPaymentOrderPrepareCreateGuard(paymentApplication)
    return {
      ...paymentApplication,
      paymentOrderPrepareGenerated: generated,
      paymentOrderPrepareGeneratedText: generated ? '已生成付款指令准备' : '未生成',
      linkedPaymentOrderPrepareId: paymentApplication.linkedPaymentOrderPrepareId || existed?.id || '',
      linkedPaymentOrderPrepareNo: paymentApplication.linkedPaymentOrderPrepareNo || existed?.paymentOrderPrepareNo || '',
      canCreatePaymentOrderPrepare: guard.canCreate,
      paymentOrderPrepareBlockReason: guard.reason,
    }
  })
}

export function createPaymentOrderPrepareFromPaymentApplication(paymentApplicationId, operator = 'page-user') {
  const paymentApplication = getPaymentApplicationById(paymentApplicationId)
  const guard = getPaymentOrderPrepareCreateGuard(paymentApplication)
  if (!guard.canCreate) {
    writePaymentInstructionPrepareLog('create_from_payment_application_blocked', {
      sourceNo: paymentApplication?.paymentApplicationNo || paymentApplicationId,
      targetId: paymentApplicationId,
      result: guard.reason,
    })
    return { success: false, error: guard.reason, paymentApplication }
  }

  const amount = roundAmount(paymentApplication.approvedAmount)
  const order = paymentOrderPrepare({
    sourcePaymentApplicationId: paymentApplication.id,
    sourcePaymentApplicationNo: paymentApplication.paymentApplicationNo,
    sourcePayableConfirmNo: paymentApplication.sourcePayableConfirmNo,
    sourceInvoicePrepareNo: paymentApplication.sourceInvoicePrepareNo,
    sourceSettlementNo: paymentApplication.sourceSettlementNo,
    supplierId: paymentApplication.supplierId,
    supplierName: paymentApplication.supplierName,
    purchaseOrderNo: paymentApplication.purchaseOrderNo,
    invoiceNo: paymentApplication.invoiceNo,
    approvedAmount: amount,
    orderAmount: amount,
    currency: paymentApplication.currency || 'CNY',
    paymentMethod: paymentApplication.paymentMethod || 'bank_transfer',
    plannedPaymentDate: paymentApplication.plannedPaymentDate || '',
    paymentPriority: paymentApplication.paymentPriority || 'normal',
    paymentPurpose: paymentApplication.paymentReason || '采购付款申请审批后的付款指令准备',
    remark: '由已审批付款申请生成付款指令准备；不付款、不生成付款凭证、不核销、不写总账、不生成银行流水。',
    createdBy: operator,
  })
  appendLog(order, 'create_from_payment_application', '', order.paymentOrderStatus, '由已审批付款申请生成付款指令准备。', operator)
  state.paymentOrderPrepares.unshift(order)
  persist()
  const writeBack = linkPaymentApplicationOrderPrepare(paymentApplication.id, order, operator)
  writePaymentInstructionPrepareLog('create_from_payment_application', {
    sourceNo: paymentApplication.paymentApplicationNo,
    targetId: order.id,
    targetNo: order.paymentOrderPrepareNo,
    result: amount,
  })
  return {
    success: true,
    paymentOrderPrepareId: order.id,
    paymentOrderPrepareNo: order.paymentOrderPrepareNo,
    paymentOrderPrepare: clone(order),
    writeBackSuccess: Boolean(writeBack?.success),
  }
}

export function recalculatePaymentOrderPrepareAmount(id, operator = 'page-user') {
  const current = byId(state.paymentOrderPrepares, id)
  if (!current) return { success: false, error: '未找到付款指令准备。' }
  if (current.paymentOrderStatus === 'closed') return { success: false, error: '已关闭的付款指令准备不能重算。' }
  const beforeStatus = current.paymentOrderStatus
  current.orderAmount = roundAmount(current.orderAmount || current.approvedAmount)
  if (current.orderAmount > current.approvedAmount) {
    current.paymentOrderStatus = 'blocked'
    current.paymentInstructionStatus = 'blocked'
    current.remark = current.remark || '指令金额超过批准金额，已阻断复核。'
  }
  current.updatedAt = nowText()
  appendLog(current, 'recalculate_order_amount', beforeStatus, current.paymentOrderStatus, '重算付款指令金额；不修改付款申请批准金额。', operator)
  persist()
  writePaymentInstructionPrepareLog('recalculate_order_amount', { targetId: current.id, targetNo: current.paymentOrderPrepareNo })
  return { success: true, paymentOrderPrepare: clone(current) }
}

export function updatePaymentOrderPrepareInfo(id, patch = {}, operator = 'page-user') {
  const current = byId(state.paymentOrderPrepares, id)
  if (!current) return { success: false, error: '未找到付款指令准备。' }
  if (['closed', 'reviewed'].includes(current.paymentOrderStatus)) return { success: false, error: '已复核或已关闭的付款指令准备不能继续编辑。' }
  const beforeStatus = current.paymentOrderStatus
  Object.assign(current, {
    orderAmount: roundAmount(patch.orderAmount ?? current.orderAmount),
    paymentMethod: patch.paymentMethod ?? current.paymentMethod,
    plannedPaymentDate: patch.plannedPaymentDate ?? current.plannedPaymentDate,
    paymentPriority: patch.paymentPriority ?? current.paymentPriority,
    paymentPurpose: patch.paymentPurpose ?? current.paymentPurpose,
    payeeName: patch.payeeName ?? current.payeeName,
    payeeBankName: patch.payeeBankName ?? current.payeeBankName,
    payeeBankAccount: patch.payeeBankAccount ?? current.payeeBankAccount,
    payerAccountName: patch.payerAccountName ?? current.payerAccountName,
    payerBankName: patch.payerBankName ?? current.payerBankName,
    payerBankAccount: patch.payerBankAccount ?? current.payerBankAccount,
    remark: patch.remark ?? current.remark,
    updatedAt: nowText(),
  })
  if (current.orderAmount > current.approvedAmount) {
    current.paymentOrderStatus = 'blocked'
    current.paymentInstructionStatus = 'blocked'
    current.remark = current.remark || '指令金额超过批准金额，已阻断复核。'
  }
  appendLog(current, 'edit_payment_order_prepare', beforeStatus, current.paymentOrderStatus, '编辑付款指令准备信息；不执行付款。', operator)
  persist()
  writePaymentInstructionPrepareLog('edit_payment_order_prepare', { targetId: current.id, targetNo: current.paymentOrderPrepareNo })
  return { success: true, paymentOrderPrepare: clone(current) }
}

function markStatus(id, nextStatus, action, patch = {}, remark = '', operator = 'page-user') {
  const current = byId(state.paymentOrderPrepares, id)
  if (!current) return { success: false, error: '未找到付款指令准备。' }
  if (current.paymentOrderStatus === 'closed' && nextStatus !== 'closed') return { success: false, error: '已关闭的付款指令准备不能继续流转。' }
  const beforeStatus = current.paymentOrderStatus
  Object.assign(current, patch, {
    paymentOrderStatus: nextStatus,
    updatedAt: nowText(),
  })
  appendLog(current, action, beforeStatus, nextStatus, remark, operator)
  persist()
  writePaymentInstructionPrepareLog(action, { targetId: current.id, targetNo: current.paymentOrderPrepareNo, result: nextStatus })
  return { success: true, paymentOrderPrepare: clone(current) }
}

export function markPaymentOrderPrepareWaitingReview(id, operator = 'page-user') {
  const current = byId(state.paymentOrderPrepares, id)
  if (!current) return { success: false, error: '未找到付款指令准备。' }
  if (current.orderAmount <= 0) return { success: false, error: '付款指令金额为空或为 0。' }
  if (current.orderAmount > current.approvedAmount) return { success: false, error: '付款指令金额超过批准金额，不能进入待复核。' }
  return markStatus(id, 'waiting_review', 'mark_waiting_review', { paymentInstructionStatus: 'not_issued' }, '标记为待复核；不签发、不执行付款。', operator)
}

export function reviewPaymentOrderPrepare(id, operator = 'page-user') {
  const current = byId(state.paymentOrderPrepares, id)
  if (!current) return { success: false, error: '未找到付款指令准备。' }
  if (!['draft', 'waiting_review'].includes(current.paymentOrderStatus)) return { success: false, error: '只有草稿或待复核状态可以复核通过。' }
  if (current.orderAmount <= 0) return { success: false, error: '付款指令金额为空或为 0。' }
  if (current.orderAmount > current.approvedAmount) return { success: false, error: '付款指令金额超过批准金额，不能复核通过。' }
  return markStatus(id, 'reviewed', 'review_payment_order_prepare', {
    paymentInstructionStatus: 'ready_to_issue',
    paymentExecutionStatus: 'not_started',
    paymentVoucherStatus: 'not_generated',
    writeOffStatus: 'not_written_off',
    ledgerStatus: 'not_written_ledger',
    postingStatus: 'not_posted',
  }, '付款指令准备复核通过；仅表示可进入后续签发，不执行付款、不生成凭证、不核销、不写总账。', operator)
}

export function blockPaymentOrderPrepare(id, remark = '付款指令准备异常阻断，待人工处理。', operator = 'page-user') {
  return markStatus(id, 'blocked', 'block_payment_order_prepare', { paymentInstructionStatus: 'blocked', remark }, remark, operator)
}

export function closePaymentOrderPrepare(id, remark = '关闭付款指令准备。', operator = 'page-user') {
  return markStatus(id, 'closed', 'close_payment_order_prepare', { remark }, remark, operator)
}

export function linkPaymentOrderPrepareExecutionPrepare(id, paymentExecutionPrepare = {}, operator = 'page-user') {
  const current = byId(state.paymentOrderPrepares, id)
  if (!current) return { success: false, error: '未找到付款指令准备。' }
  const beforeStatus = current.paymentInstructionStatus || current.paymentOrderStatus
  current.linkedPaymentExecutionPrepareId = paymentExecutionPrepare.id || paymentExecutionPrepare.paymentExecutionPrepareId || current.linkedPaymentExecutionPrepareId || ''
  current.linkedPaymentExecutionPrepareNo = paymentExecutionPrepare.paymentExecutionPrepareNo || current.linkedPaymentExecutionPrepareNo || ''
  current.paymentExecutionPrepareGeneratedAt = current.paymentExecutionPrepareGeneratedAt || nowText()
  current.paymentExecutionPrepareGeneratedBy = operator
  current.paymentInstructionStatus = 'issued_for_execution'
  current.paymentExecutionStatus = current.paymentExecutionStatus || 'not_started'
  current.paymentVoucherStatus = current.paymentVoucherStatus || 'not_generated'
  current.writeOffStatus = current.writeOffStatus || 'not_written_off'
  current.ledgerStatus = current.ledgerStatus || 'not_written_ledger'
  current.postingStatus = current.postingStatus || 'not_posted'
  current.updatedAt = nowText()
  appendLog(
    current,
    'link_payment_execution_prepare',
    beforeStatus,
    current.paymentInstructionStatus,
    `已签发到付款执行准备 ${current.linkedPaymentExecutionPrepareNo || '-'}；不代表已付款。`,
    operator,
  )
  persist()
  writePaymentInstructionPrepareLog('link_payment_execution_prepare', {
    sourceNo: current.paymentOrderPrepareNo,
    targetId: current.linkedPaymentExecutionPrepareId,
    targetNo: current.linkedPaymentExecutionPrepareNo,
    result: '仅回写付款执行准备关联字段；issued_for_execution 不代表已付款。',
  })
  return { success: true, paymentOrderPrepare: clone(current) }
}
