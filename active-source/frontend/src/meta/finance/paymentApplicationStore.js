import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  getAccountPayableConfirmById,
  linkAccountPayableConfirmPaymentApplication,
  listAccountPayableConfirms,
} from './accountPayableConfirmStore.js'

const STORAGE_KEY = 'payment-application-state-v1'
const ACTIVE_STATUSES = ['draft', 'waiting_submit', 'submitted', 'approved', 'blocked']

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
  return { paymentApplications: [] }
}

function byId(collection, id) {
  return (collection || []).find((item) => String(item.id) === String(id)) || null
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[PAYMENT APPLICATION STORE] fallback to empty state', error)
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
      sourcePayableConfirmNo: current.sourcePayableConfirmNo || '',
      paymentApplicationNo: current.paymentApplicationNo || '',
    },
  ]
}

function paymentApplication(payload = {}) {
  const stamp = nowText()
  const payableAmount = roundAmount(payload.payableAmount ?? payload.confirmedPayableAmount)
  const applicationAmount = roundAmount(payload.applicationAmount ?? payableAmount)
  return {
    id: payload.id || createId('payment-application'),
    paymentApplicationNo: payload.paymentApplicationNo || createNo('PAP'),
    sourcePayableConfirmId: payload.sourcePayableConfirmId || '',
    sourcePayableConfirmNo: payload.sourcePayableConfirmNo || '',
    sourceInvoicePrepareNo: payload.sourceInvoicePrepareNo || '',
    sourceSettlementNo: payload.sourceSettlementNo || '',
    supplierId: payload.supplierId || '',
    supplierName: payload.supplierName || '',
    purchaseOrderNo: payload.purchaseOrderNo || '',
    invoiceNo: payload.invoiceNo || '',
    invoiceDate: payload.invoiceDate || '',
    payableAmount,
    applicationAmount,
    approvedAmount: roundAmount(payload.approvedAmount),
    currency: payload.currency || 'CNY',
    paymentMethod: payload.paymentMethod || 'bank_transfer',
    plannedPaymentDate: payload.plannedPaymentDate || '',
    paymentReason: payload.paymentReason || '采购应付确认后的付款申请准备',
    paymentPriority: payload.paymentPriority || 'normal',
    paymentApplicationStatus: payload.paymentApplicationStatus || 'draft',
    paymentApprovalStatus: payload.paymentApprovalStatus || 'not_submitted',
    paymentExecutionStatus: payload.paymentExecutionStatus || 'not_started',
    paymentVoucherStatus: payload.paymentVoucherStatus || 'not_generated',
    writeOffStatus: payload.writeOffStatus || 'not_written_off',
    ledgerStatus: payload.ledgerStatus || 'not_written_ledger',
    postingStatus: payload.postingStatus || 'not_posted',
    linkedPaymentOrderPrepareId: payload.linkedPaymentOrderPrepareId || '',
    linkedPaymentOrderPrepareNo: payload.linkedPaymentOrderPrepareNo || '',
    paymentOrderPrepareGeneratedAt: payload.paymentOrderPrepareGeneratedAt || '',
    paymentOrderPrepareGeneratedBy: payload.paymentOrderPrepareGeneratedBy || '',
    isDemoChain: Boolean(payload.isDemoChain),
    demoChainVersion: payload.demoChainVersion || '',
    demoChainGeneratedAt: payload.demoChainGeneratedAt || '',
    demoChainPurpose: payload.demoChainPurpose || '',
    remark: payload.remark || '',
    downstreamActionCode: payload.downstreamActionCode || '',
    downstreamObjectType: payload.downstreamObjectType || '',
    downstreamObjectNo: payload.downstreamObjectNo || '',
    downstreamObjectId: payload.downstreamObjectId || '',
    downstreamGeneratedAt: payload.downstreamGeneratedAt || '',
    flowWritebackStatus: payload.flowWritebackStatus || '',
    nextStepReleaseStatus: payload.nextStepReleaseStatus || '',
    sourceObjectType: payload.sourceObjectType || '',
    sourceObjectNo: payload.sourceObjectNo || '',
    sourceObjectId: payload.sourceObjectId || '',
    sourceBusinessRoute: payload.sourceBusinessRoute || '',
    createdFromActionCode: payload.createdFromActionCode || '',
    sourceLinkStatus: payload.sourceLinkStatus || '',
    createdAt: payload.createdAt || stamp,
    createdBy: payload.createdBy || 'system',
    updatedAt: payload.updatedAt || stamp,
    logs: Array.isArray(payload.logs) ? payload.logs : [],
  }
}

function normalizeState(raw = {}) {
  return { paymentApplications: (raw.paymentApplications || []).map(paymentApplication) }
}

let state = loadState()

export function writePaymentApplicationLog(action, payload = {}) {
  addOperationLog({
    module: '付款申请准备',
    action,
    targetType: payload.targetType || 'paymentApplication',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源应付确认：${payload.sourceNo || '-'}`,
      `目标付款申请：${payload.targetNo || '-'}`,
      `结果：${payload.result || '成功'}`,
    ].join('；'),
  })
}

export function getPaymentApplicationState() {
  return clone(state)
}

export function savePaymentApplicationState(nextState) {
  state = normalizeState(nextState)
  persist()
  writePaymentApplicationLog('保存付款申请准备状态', { targetType: 'paymentApplicationState', targetId: 'state' })
  return getPaymentApplicationState()
}

export function listPaymentApplications() {
  return clone(state.paymentApplications)
}

export function getPaymentApplicationById(id) {
  return clone(byId(state.paymentApplications, id))
}

export function isPaymentApplicationGeneratedFromPayableConfirm(payableConfirmOrId) {
  const payableConfirm = typeof payableConfirmOrId === 'object'
    ? payableConfirmOrId
    : getAccountPayableConfirmById(payableConfirmOrId)
  if (!payableConfirm?.id) return false
  if (payableConfirm.linkedPaymentApplicationId || payableConfirm.linkedPaymentApplicationNo) return true
  return state.paymentApplications.some((item) => (
    String(item.sourcePayableConfirmId) === String(payableConfirm.id)
    && ACTIVE_STATUSES.includes(item.paymentApplicationStatus)
  ))
}

export function getPaymentApplicationCreateGuard(payableConfirm = {}) {
  if (!payableConfirm?.id) return { canCreate: false, reason: '未找到应付确认准备。' }
  if (isPaymentApplicationGeneratedFromPayableConfirm(payableConfirm)) return { canCreate: false, reason: '已存在付款申请准备，不能重复生成。' }
  if (payableConfirm.payableConfirmStatus !== 'confirmed') return { canCreate: false, reason: '应付尚未确认。' }
  if (payableConfirm.payableStatus !== 'confirmed_pending_payment') return { canCreate: false, reason: '应付状态不是已确认待后续付款。' }
  if (payableConfirm.paymentPlanStatus !== 'not_started') return { canCreate: false, reason: '已进入付款计划或付款申请阶段。' }
  if (payableConfirm.writeOffStatus !== 'not_written_off') return { canCreate: false, reason: '核销状态不是未核销。' }
  if (payableConfirm.ledgerStatus !== 'not_written_ledger') return { canCreate: false, reason: '总账状态不是未写总账。' }
  if (payableConfirm.postingStatus !== 'not_posted') return { canCreate: false, reason: '过账状态不是未过账。' }
  if (['blocked', 'closed'].includes(payableConfirm.payableConfirmStatus)) return { canCreate: false, reason: '应付确认准备已阻断或关闭。' }
  const amount = roundAmount(payableConfirm.confirmedPayableAmount || payableConfirm.payableAmount)
  if (amount <= 0) return { canCreate: false, reason: '应付金额为空或为 0。' }
  return { canCreate: true, reason: '' }
}

export function getPaymentApplicationSourcesFromPayableConfirms() {
  return listAccountPayableConfirms().map((payableConfirm) => {
    const generated = isPaymentApplicationGeneratedFromPayableConfirm(payableConfirm)
    const existed = state.paymentApplications.find((item) => (
      String(item.sourcePayableConfirmId) === String(payableConfirm.id)
      && ACTIVE_STATUSES.includes(item.paymentApplicationStatus)
    ))
    const guard = getPaymentApplicationCreateGuard(payableConfirm)
    return {
      ...payableConfirm,
      paymentApplicationGenerated: generated,
      paymentApplicationGeneratedText: generated ? '已生成付款申请准备' : '未生成',
      linkedPaymentApplicationId: payableConfirm.linkedPaymentApplicationId || existed?.id || '',
      linkedPaymentApplicationNo: payableConfirm.linkedPaymentApplicationNo || existed?.paymentApplicationNo || '',
      canCreatePaymentApplication: guard.canCreate,
      paymentApplicationBlockReason: guard.reason,
    }
  })
}

export function createPaymentApplicationFromPayableConfirm(payableConfirmId, operator = 'page-user') {
  const payableConfirm = getAccountPayableConfirmById(payableConfirmId)
  const guard = getPaymentApplicationCreateGuard(payableConfirm)
  if (!guard.canCreate) {
    writePaymentApplicationLog('create_from_payable_confirm_blocked', {
      sourceNo: payableConfirm?.payableConfirmNo || payableConfirmId,
      targetId: payableConfirmId,
      result: guard.reason,
    })
    return { success: false, error: guard.reason, accountPayableConfirm: payableConfirm }
  }

  const amount = roundAmount(payableConfirm.confirmedPayableAmount || payableConfirm.payableAmount)
  const application = paymentApplication({
    sourcePayableConfirmId: payableConfirm.id,
    sourcePayableConfirmNo: payableConfirm.payableConfirmNo,
    sourceInvoicePrepareNo: payableConfirm.sourceInvoicePrepareNo,
    sourceSettlementNo: payableConfirm.sourceSettlementNo,
    supplierId: payableConfirm.supplierId,
    supplierName: payableConfirm.supplierName,
    purchaseOrderNo: payableConfirm.purchaseOrderNo,
    invoiceNo: payableConfirm.invoiceNo,
    invoiceDate: payableConfirm.invoiceDate,
    payableAmount: amount,
    applicationAmount: amount,
    currency: payableConfirm.currency || 'CNY',
    remark: '由已确认应付生成付款申请准备；不付款、不生成付款凭证、不核销、不写总账、不生成银行流水。',
    createdBy: operator,
  })
  appendLog(application, 'create_from_payable_confirm', '', application.paymentApplicationStatus, '由已确认应付生成付款申请准备。', operator)
  state.paymentApplications.unshift(application)
  persist()
  const writeBack = linkAccountPayableConfirmPaymentApplication(payableConfirm.id, application, operator)
  writePaymentApplicationLog('create_from_payable_confirm', {
    sourceNo: payableConfirm.payableConfirmNo,
    targetId: application.id,
    targetNo: application.paymentApplicationNo,
    result: amount,
  })
  return {
    success: true,
    paymentApplicationId: application.id,
    paymentApplicationNo: application.paymentApplicationNo,
    paymentApplication: clone(application),
    writeBackSuccess: Boolean(writeBack?.success),
  }
}

export function recalculatePaymentApplicationAmount(id, operator = 'page-user') {
  const current = byId(state.paymentApplications, id)
  if (!current) return { success: false, error: '未找到付款申请准备。' }
  if (['closed'].includes(current.paymentApplicationStatus)) return { success: false, error: '已关闭的付款申请准备不能重算。' }
  const beforeStatus = current.paymentApplicationStatus
  current.applicationAmount = roundAmount(current.applicationAmount || current.payableAmount)
  if (current.applicationAmount > current.payableAmount) {
    current.paymentApplicationStatus = 'blocked'
    current.remark = current.remark || '申请金额超过应付金额，已阻断。'
  }
  current.updatedAt = nowText()
  appendLog(current, 'recalculate_application_amount', beforeStatus, current.paymentApplicationStatus, '重算申请金额，仅更新付款申请准备对象。', operator)
  persist()
  writePaymentApplicationLog('recalculate_application_amount', { targetId: current.id, targetNo: current.paymentApplicationNo })
  return { success: true, paymentApplication: clone(current) }
}

export function updatePaymentApplicationInfo(id, patch = {}, operator = 'page-user') {
  const current = byId(state.paymentApplications, id)
  if (!current) return { success: false, error: '未找到付款申请准备。' }
  if (['closed', 'approved'].includes(current.paymentApplicationStatus)) return { success: false, error: '已关闭或已审批通过的付款申请准备不能编辑。' }
  const beforeStatus = current.paymentApplicationStatus
  const nextAmount = roundAmount(patch.applicationAmount ?? current.applicationAmount)
  Object.assign(current, {
    applicationAmount: nextAmount,
    paymentMethod: patch.paymentMethod ?? current.paymentMethod,
    plannedPaymentDate: patch.plannedPaymentDate ?? current.plannedPaymentDate,
    paymentReason: patch.paymentReason ?? current.paymentReason,
    paymentPriority: patch.paymentPriority ?? current.paymentPriority,
    remark: patch.remark ?? current.remark,
    updatedAt: nowText(),
  })
  if (nextAmount > current.payableAmount) {
    current.paymentApplicationStatus = 'blocked'
    current.paymentApprovalStatus = 'rejected'
    current.remark = current.remark || '申请金额超过应付金额，已阻断。'
  }
  appendLog(current, 'edit_payment_application', beforeStatus, current.paymentApplicationStatus, '编辑付款申请准备信息。', operator)
  persist()
  writePaymentApplicationLog('edit_payment_application', { targetId: current.id, targetNo: current.paymentApplicationNo })
  return { success: true, paymentApplication: clone(current) }
}

function markStatus(id, nextStatus, action, patch = {}, remark = '', operator = 'page-user') {
  const current = byId(state.paymentApplications, id)
  if (!current) return { success: false, error: '未找到付款申请准备。' }
  if (current.paymentApplicationStatus === 'closed' && nextStatus !== 'closed') return { success: false, error: '已关闭的付款申请准备不能继续流转。' }
  const beforeStatus = current.paymentApplicationStatus
  Object.assign(current, patch, { paymentApplicationStatus: nextStatus, updatedAt: nowText() })
  appendLog(current, action, beforeStatus, nextStatus, remark, operator)
  persist()
  writePaymentApplicationLog(action, { targetId: current.id, targetNo: current.paymentApplicationNo, result: nextStatus })
  return { success: true, paymentApplication: clone(current) }
}

export function markPaymentApplicationWaitingSubmit(id, operator = 'page-user') {
  const current = byId(state.paymentApplications, id)
  if (!current) return { success: false, error: '未找到付款申请准备。' }
  if (current.applicationAmount > current.payableAmount) return { success: false, error: '申请金额超过应付金额，不能进入待提交。' }
  return markStatus(id, 'waiting_submit', 'mark_waiting_submit', { paymentApprovalStatus: 'not_submitted' }, '标记为待提交。', operator)
}

export function submitPaymentApplication(id, operator = 'page-user') {
  const current = byId(state.paymentApplications, id)
  if (!current) return { success: false, error: '未找到付款申请准备。' }
  if (!['draft', 'waiting_submit'].includes(current.paymentApplicationStatus)) return { success: false, error: '只有草稿或待提交状态可以提交。' }
  if (current.applicationAmount <= 0) return { success: false, error: '申请金额为空或为 0。' }
  if (current.applicationAmount > current.payableAmount) return { success: false, error: '申请金额超过应付金额，不能提交。' }
  return markStatus(id, 'submitted', 'submit_payment_application', { paymentApprovalStatus: 'pending_review' }, '提交付款申请准备，仅进入审批准备。', operator)
}

export function approvePaymentApplication(id, operator = 'page-user') {
  const current = byId(state.paymentApplications, id)
  if (!current) return { success: false, error: '未找到付款申请准备。' }
  if (current.paymentApplicationStatus !== 'submitted' || current.paymentApprovalStatus !== 'pending_review') return { success: false, error: '只有已提交且待审批的付款申请准备可以审批通过。' }
  if (current.applicationAmount <= 0) return { success: false, error: '申请金额为空或为 0。' }
  if (current.applicationAmount > current.payableAmount) return { success: false, error: '申请金额超过应付金额，不能审批通过。' }
  return markStatus(id, 'approved', 'approve_payment_application', {
    paymentApprovalStatus: 'approved',
    approvedAmount: roundAmount(current.applicationAmount),
    paymentExecutionStatus: 'not_started',
    paymentVoucherStatus: 'not_generated',
    writeOffStatus: 'not_written_off',
    ledgerStatus: 'not_written_ledger',
    postingStatus: 'not_posted',
  }, '审批通过，仅代表付款申请准备通过；不执行付款、不生成付款凭证、不核销、不写总账。', operator)
}

export function rejectPaymentApplication(id, remark = '付款申请准备审批驳回。', operator = 'page-user') {
  return markStatus(id, 'blocked', 'reject_payment_application', { paymentApprovalStatus: 'rejected', remark }, remark, operator)
}

export function blockPaymentApplication(id, remark = '付款申请准备异常阻断，待人工处理。', operator = 'page-user') {
  return markStatus(id, 'blocked', 'block_payment_application', { remark }, remark, operator)
}

export function closePaymentApplication(id, remark = '关闭付款申请准备。', operator = 'page-user') {
  return markStatus(id, 'closed', 'close_payment_application', { remark }, remark, operator)
}

export function linkPaymentApplicationOrderPrepare(id, paymentOrderPrepare = {}, operator = 'page-user') {
  const current = byId(state.paymentApplications, id)
  if (!current) return { success: false, error: '未找到付款申请准备。' }
  const beforeStatus = `${current.paymentApplicationStatus || ''}/${current.paymentApprovalStatus || ''}`
  current.linkedPaymentOrderPrepareId = paymentOrderPrepare.id || paymentOrderPrepare.paymentOrderPrepareId || current.linkedPaymentOrderPrepareId || ''
  current.linkedPaymentOrderPrepareNo = paymentOrderPrepare.paymentOrderPrepareNo || current.linkedPaymentOrderPrepareNo || ''
  current.paymentOrderPrepareGeneratedAt = current.paymentOrderPrepareGeneratedAt || nowText()
  current.paymentOrderPrepareGeneratedBy = operator
  current.updatedAt = nowText()
  appendLog(
    current,
    'link_payment_order_prepare',
    beforeStatus,
    `${current.paymentApplicationStatus || ''}/${current.paymentApprovalStatus || ''}`,
    `已关联付款指令准备 ${current.linkedPaymentOrderPrepareNo || '-'}`,
    operator,
  )
  persist()
  writePaymentApplicationLog('link_payment_order_prepare', {
    sourceNo: current.paymentApplicationNo,
    targetId: current.linkedPaymentOrderPrepareId,
    targetNo: current.linkedPaymentOrderPrepareNo,
    result: '仅回写付款指令准备关联字段',
  })
  return { success: true, paymentApplication: clone(current) }
}
