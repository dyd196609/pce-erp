import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  getInvoicePrepareById,
  linkInvoicePreparePayableConfirm,
  listInvoicePrepares,
} from './invoicePrepareStore.js'

const STORAGE_KEY = 'account-payable-confirm-state-v1'

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
  return { accountPayableConfirms: [] }
}

function byId(collection, id) {
  return (collection || []).find((item) => String(item.id) === String(id)) || null
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
      sourceInvoicePrepareNo: current.sourceInvoicePrepareNo || '',
      sourceSettlementNo: current.sourceSettlementNo || '',
      payableConfirmNo: current.payableConfirmNo || '',
    },
  ]
}

function amountDifferenceReason(totalInvoiceAmount, settlementAmount) {
  if (!settlementAmount) return '来源结算金额待补充，仅提示不调账。'
  const difference = roundAmount(totalInvoiceAmount - settlementAmount)
  if (Math.abs(difference) < 0.01) return ''
  return `发票价税合计与来源结算金额差异 ${difference.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}，请核对税额、扣款、折让或多供应商拆分。`
}

function accountPayableConfirm(payload = {}) {
  const stamp = nowText()
  const totalInvoiceAmount = roundAmount(payload.totalInvoiceAmount)
  const payableAmount = roundAmount(payload.payableAmount ?? totalInvoiceAmount)
  const sourceSettlementAmount = roundAmount(payload.sourceSettlementAmount)
  const amountDifference = roundAmount(totalInvoiceAmount - sourceSettlementAmount)
  return {
    id: payload.id || createId('apc'),
    payableConfirmNo: payload.payableConfirmNo || createNo('APC'),
    sourceInvoicePrepareId: payload.sourceInvoicePrepareId || '',
    sourceInvoicePrepareNo: payload.sourceInvoicePrepareNo || '',
    sourceSettlementNo: payload.sourceSettlementNo || '',
    supplierId: payload.supplierId || '',
    supplierName: payload.supplierName || '',
    purchaseOrderNo: payload.purchaseOrderNo || payload.sourcePurchaseOrderNo || '',
    invoiceNo: payload.invoiceNo || '',
    invoiceDate: payload.invoiceDate || '',
    invoiceType: payload.invoiceType || 'specialVat',
    invoiceAmount: roundAmount(payload.invoiceAmount),
    taxRate: toNumber(payload.taxRate),
    taxAmount: roundAmount(payload.taxAmount),
    totalInvoiceAmount,
    payableAmount,
    confirmedPayableAmount: roundAmount(payload.confirmedPayableAmount ?? payableAmount),
    currency: payload.currency || 'CNY',
    payableStatus: payload.payableStatus || 'not_confirmed',
    payableConfirmStatus: payload.payableConfirmStatus || 'draft',
    invoiceCheckStatus: payload.invoiceCheckStatus || payload.sourceInvoiceStatus || 'checked',
    sourceInvoiceStatus: payload.sourceInvoiceStatus || '',
    sourceInvoicePrepareStatus: payload.sourceInvoicePrepareStatus || '',
    sourceSettlementAmount,
    amountDifference,
    amountDifferenceReason: payload.amountDifferenceReason || amountDifferenceReason(totalInvoiceAmount, sourceSettlementAmount),
    paymentPlanStatus: payload.paymentPlanStatus || 'not_started',
    writeOffStatus: payload.writeOffStatus || 'not_written_off',
    ledgerStatus: payload.ledgerStatus || 'not_written_ledger',
    postingStatus: payload.postingStatus || 'not_posted',
    linkedPaymentApplicationId: payload.linkedPaymentApplicationId || '',
    linkedPaymentApplicationNo: payload.linkedPaymentApplicationNo || '',
    paymentApplicationGeneratedAt: payload.paymentApplicationGeneratedAt || '',
    paymentApplicationGeneratedBy: payload.paymentApplicationGeneratedBy || '',
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
  return { accountPayableConfirms: (raw.accountPayableConfirms || []).map(accountPayableConfirm) }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[ACCOUNT PAYABLE CONFIRM STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export function writePayableConfirmLog(action, payload = {}) {
  addOperationLog({
    module: '应付确认准备',
    action,
    targetType: payload.targetType || 'accountPayableConfirm',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源单据：${payload.sourceNo || '-'}`,
      `目标单据：${payload.targetNo || '-'}`,
      `结果：${payload.result || '成功'}`,
    ].join('；'),
  })
}

export function getAccountPayableConfirmState() {
  return clone(state)
}

export function saveAccountPayableConfirmState(nextState) {
  state = normalizeState(nextState)
  persist()
  writePayableConfirmLog('保存应付确认准备状态', { targetType: 'accountPayableConfirmState', targetId: 'state' })
  return getAccountPayableConfirmState()
}

export function listAccountPayableConfirms() {
  return clone(state.accountPayableConfirms)
}

export function getAccountPayableConfirmById(id) {
  return clone(byId(state.accountPayableConfirms, id))
}

export function isPayableConfirmGeneratedFromInvoicePrepare(invoicePrepareOrId) {
  const prepare = typeof invoicePrepareOrId === 'object' ? invoicePrepareOrId : getInvoicePrepareById(invoicePrepareOrId)
  if (!prepare?.id) return false
  if (prepare.linkedPayableConfirmId || prepare.linkedPayableConfirmNo) return true
  return state.accountPayableConfirms.some((item) => String(item.sourceInvoicePrepareId) === String(prepare.id))
}

export function getPayableConfirmCreateGuard(prepare = {}) {
  if (!prepare?.id) return { canCreate: false, reason: '未找到采购发票准备记录。' }
  if (isPayableConfirmGeneratedFromInvoicePrepare(prepare)) return { canCreate: false, reason: '已存在应付确认准备，不能重复生成。' }
  if (prepare.invoicePrepareStatus === 'closed') return { canCreate: false, reason: '发票准备已关闭，不能生成应付确认准备。' }
  if (prepare.invoicePrepareStatus === 'blocked') return { canCreate: false, reason: '发票准备异常阻断，不能生成应付确认准备。' }
  if (prepare.invoiceStatus !== 'checked') return { canCreate: false, reason: '发票尚未核对通过。' }
  if (prepare.invoicePrepareStatus !== 'checked') return { canCreate: false, reason: '只有已核对通过的发票准备可生成应付确认准备。' }
  if (!prepare.invoiceNo) return { canCreate: false, reason: '缺少发票号码。' }
  if (!prepare.invoiceDate) return { canCreate: false, reason: '缺少发票日期。' }
  if (!toNumber(prepare.totalInvoiceAmount)) return { canCreate: false, reason: '价税合计为空或为 0。' }
  return { canCreate: true, reason: '' }
}

export function getPayableConfirmSourcesFromInvoicePrepares() {
  return listInvoicePrepares().map((prepare) => {
    const generated = isPayableConfirmGeneratedFromInvoicePrepare(prepare)
    const guard = getPayableConfirmCreateGuard(prepare)
    const existed = state.accountPayableConfirms.find((item) => String(item.sourceInvoicePrepareId) === String(prepare.id))
    return {
      ...prepare,
      payableConfirmGenerated: generated,
      payableConfirmGeneratedText: generated ? '已生成应付确认准备' : '未生成',
      linkedPayableConfirmId: prepare.linkedPayableConfirmId || existed?.id || '',
      linkedPayableConfirmNo: prepare.linkedPayableConfirmNo || existed?.payableConfirmNo || '',
      canCreatePayableConfirm: guard.canCreate,
      payableConfirmBlockReason: guard.reason,
    }
  })
}

export function createPayableConfirmFromInvoicePrepare(invoicePrepareId, operator = 'page-user') {
  const prepare = getInvoicePrepareById(invoicePrepareId)
  const guard = getPayableConfirmCreateGuard(prepare)
  if (!guard.canCreate) {
    writePayableConfirmLog('create_from_invoice_prepare_blocked', {
      sourceNo: prepare?.invoicePrepareNo || invoicePrepareId,
      targetId: invoicePrepareId,
      result: guard.reason,
    })
    return { success: false, error: guard.reason, invoicePrepare: prepare }
  }
  const confirm = accountPayableConfirm({
    sourceInvoicePrepareId: prepare.id,
    sourceInvoicePrepareNo: prepare.invoicePrepareNo,
    sourceSettlementNo: prepare.sourceSettlementNo,
    supplierId: prepare.supplierId,
    supplierName: prepare.supplierName,
    purchaseOrderNo: prepare.purchaseOrderNo || prepare.sourcePurchaseOrderNo,
    invoiceNo: prepare.invoiceNo,
    invoiceDate: prepare.invoiceDate,
    invoiceType: prepare.invoiceType,
    invoiceAmount: prepare.invoiceAmount,
    taxRate: prepare.taxRate,
    taxAmount: prepare.taxAmount,
    totalInvoiceAmount: prepare.totalInvoiceAmount,
    payableAmount: prepare.totalInvoiceAmount,
    confirmedPayableAmount: prepare.totalInvoiceAmount,
    invoiceCheckStatus: prepare.invoiceStatus,
    sourceInvoiceStatus: prepare.invoiceStatus,
    sourceInvoicePrepareStatus: prepare.invoicePrepareStatus,
    sourceSettlementAmount: prepare.settlementAmount,
    remark: '由采购发票准备生成，仅作为应付确认准备；不付款、不核销、不写总账、不生成银行流水。',
    createdBy: operator,
  })
  appendLog(confirm, 'create_from_invoice_prepare', '', confirm.payableConfirmStatus, '由已核对通过的采购发票准备生成应付确认准备。', operator)
  state.accountPayableConfirms.unshift(confirm)
  persist()
  const writeBack = linkInvoicePreparePayableConfirm(prepare.id, confirm, operator)
  writePayableConfirmLog('create_from_invoice_prepare', {
    sourceNo: prepare.invoicePrepareNo,
    targetId: confirm.id,
    targetNo: confirm.payableConfirmNo,
    result: confirm.payableAmount,
  })
  return { success: true, payableConfirmId: confirm.id, payableConfirmNo: confirm.payableConfirmNo, accountPayableConfirm: clone(confirm), writeBackSuccess: Boolean(writeBack?.success) }
}

export function recalculatePayableConfirmAmount(id, operator = 'page-user') {
  const current = byId(state.accountPayableConfirms, id)
  if (!current) return { success: false, error: '未找到应付确认准备。' }
  if (['closed'].includes(current.payableConfirmStatus)) return { success: false, error: '已关闭的应付确认准备不能重算。' }
  const beforeStatus = current.payableConfirmStatus
  current.payableAmount = roundAmount(current.totalInvoiceAmount)
  current.confirmedPayableAmount = roundAmount(current.confirmedPayableAmount || current.payableAmount)
  current.amountDifference = roundAmount(current.totalInvoiceAmount - current.sourceSettlementAmount)
  current.amountDifferenceReason = amountDifferenceReason(current.totalInvoiceAmount, current.sourceSettlementAmount)
  current.updatedAt = nowText()
  appendLog(current, 'recalculate_payable_amount', beforeStatus, current.payableConfirmStatus, '重算应付金额，仅更新应付确认准备对象。', operator)
  persist()
  writePayableConfirmLog('recalculate_payable_amount', { targetId: current.id, targetNo: current.payableConfirmNo })
  return { success: true, accountPayableConfirm: clone(current) }
}

function markStatus(id, nextStatus, action, patch = {}, remark = '', operator = 'page-user') {
  const current = byId(state.accountPayableConfirms, id)
  if (!current) return { success: false, error: '未找到应付确认准备。' }
  if (current.payableConfirmStatus === 'closed' && nextStatus !== 'closed') return { success: false, error: '已关闭的应付确认准备不能继续流转。' }
  const beforeStatus = current.payableConfirmStatus
  Object.assign(current, patch, { payableConfirmStatus: nextStatus, updatedAt: nowText() })
  appendLog(current, action, beforeStatus, nextStatus, remark, operator)
  persist()
  writePayableConfirmLog(action, { targetId: current.id, targetNo: current.payableConfirmNo, result: nextStatus })
  return { success: true, accountPayableConfirm: clone(current) }
}

export function markPayableConfirmWaiting(id, operator = 'page-user') {
  return markStatus(id, 'waiting_confirm', 'mark_waiting_confirm', { payableStatus: 'not_confirmed' }, '标记为待确认。', operator)
}

export function confirmAccountPayable(id, operator = 'page-user') {
  const current = byId(state.accountPayableConfirms, id)
  if (!current) return { success: false, error: '未找到应付确认准备。' }
  if (!['draft', 'waiting_confirm'].includes(current.payableConfirmStatus)) return { success: false, error: '只有草稿或待确认状态可以确认应付。' }
  if (current.invoiceCheckStatus !== 'checked') return { success: false, error: '来源发票未核对通过。' }
  if (!toNumber(current.totalInvoiceAmount)) return { success: false, error: '价税合计为空，不能确认应付。' }
  return markStatus(id, 'confirmed', 'confirm_payable', {
    payableStatus: 'confirmed_pending_payment',
    paymentPlanStatus: 'not_started',
    writeOffStatus: 'not_written_off',
    ledgerStatus: 'not_written_ledger',
    postingStatus: 'not_posted',
    confirmedPayableAmount: roundAmount(current.payableAmount || current.totalInvoiceAmount),
  }, '确认应付，仅表示可进入后续付款计划或付款申请；本轮不生成付款。', operator)
}

export function blockPayableConfirm(id, remark = '应付确认准备异常阻断，待人工处理。', operator = 'page-user') {
  return markStatus(id, 'blocked', 'mark_payable_blocked', { payableStatus: 'not_confirmed', remark }, remark, operator)
}

export function closePayableConfirm(id, remark = '关闭应付确认准备。', operator = 'page-user') {
  return markStatus(id, 'closed', 'close_payable_confirm', { remark }, remark, operator)
}

export function linkAccountPayableConfirmPaymentApplication(id, paymentApplication = {}, operator = 'page-user') {
  const current = byId(state.accountPayableConfirms, id)
  if (!current) return { success: false, error: '未找到应付确认准备。' }
  const beforeStatus = `${current.payableConfirmStatus || ''}/${current.payableStatus || ''}`
  current.linkedPaymentApplicationId = paymentApplication.id || paymentApplication.paymentApplicationId || current.linkedPaymentApplicationId || ''
  current.linkedPaymentApplicationNo = paymentApplication.paymentApplicationNo || current.linkedPaymentApplicationNo || ''
  current.paymentApplicationGeneratedAt = current.paymentApplicationGeneratedAt || nowText()
  current.paymentApplicationGeneratedBy = operator
  current.updatedAt = nowText()
  appendLog(
    current,
    'link_payment_application_prepare',
    beforeStatus,
    `${current.payableConfirmStatus || ''}/${current.payableStatus || ''}`,
    `已关联付款申请准备 ${current.linkedPaymentApplicationNo || '-'}`,
    operator,
  )
  persist()
  writePayableConfirmLog('link_payment_application_prepare', {
    sourceNo: current.payableConfirmNo,
    targetId: current.linkedPaymentApplicationId,
    targetNo: current.linkedPaymentApplicationNo,
    result: '仅回写付款申请准备关联字段',
  })
  return { success: true, accountPayableConfirm: clone(current) }
}
