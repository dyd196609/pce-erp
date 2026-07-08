import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import { getInvoicePrepareById, listInvoicePrepares, markInvoicePrepareApDraftGenerated } from './invoicePrepareStore.js'

const STORAGE_KEY = 'account-payable-draft-state-v1'
const SOURCE_READY_STATUSES = ['matched', 'payableReady']

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function nowText() {
  return new Date().toISOString()
}

function today() {
  return new Date().toISOString().slice(0, 10)
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
  return { accountPayableDrafts: [] }
}

function byId(collection, id) {
  return (collection || []).find((item) => String(item.id) === String(id)) || null
}

function normalizeLine(line = {}, index = 0) {
  const invoiceAmount = roundAmount(line.invoiceAmount ?? line.checkedAmount)
  return {
    id: line.id || createId('apdl'),
    lineNo: line.lineNo || index + 1,
    materialId: line.materialId || '',
    materialCode: line.materialCode || '',
    materialName: line.materialName || '',
    spec: line.spec || line.specification || '',
    unit: line.unit || '',
    checkedQty: toNumber(line.checkedQty),
    checkedPrice: toNumber(line.checkedPrice),
    checkedAmount: roundAmount(line.checkedAmount),
    noTaxAmount: roundAmount(line.noTaxAmount),
    taxRate: toNumber(line.taxRate),
    taxAmount: roundAmount(line.taxAmount),
    invoiceAmount,
    payableAmount: roundAmount(line.payableAmount ?? invoiceAmount),
    sourceInvoicePrepareLineId: line.sourceInvoicePrepareLineId || line.id || '',
    sourcePayableCheckLineId: line.sourcePayableCheckLineId || '',
    sourceInventoryTransactionId: line.sourceInventoryTransactionId || '',
    sourceInventoryTransactionNo: line.sourceInventoryTransactionNo || '',
    sourcePurchaseOrderNo: line.sourcePurchaseOrderNo || '',
    sourceReceiveNo: line.sourceReceiveNo || '',
    sourceInspectionNo: line.sourceInspectionNo || '',
    rootRequestNo: line.rootRequestNo || '',
    remark: line.remark || '',
  }
}

function summarizeLines(lines = []) {
  const totalInvoiceAmount = roundAmount(lines.reduce((sum, line) => sum + toNumber(line.invoiceAmount), 0))
  return {
    totalNoTaxAmount: roundAmount(lines.reduce((sum, line) => sum + toNumber(line.noTaxAmount), 0)),
    totalTaxAmount: roundAmount(lines.reduce((sum, line) => sum + toNumber(line.taxAmount), 0)),
    totalInvoiceAmount,
    totalPayableAmount: totalInvoiceAmount,
  }
}

function accountPayableDraft(payload = {}) {
  const stamp = nowText()
  const lines = (payload.lines || []).map(normalizeLine)
  const summary = summarizeLines(lines)
  const totalPayableAmount = roundAmount(payload.totalPayableAmount ?? summary.totalPayableAmount)
  const paidAmount = roundAmount(payload.paidAmount ?? 0)
  return {
    id: payload.id || createId('apd'),
    apDraftNo: payload.apDraftNo || createNo('APD'),
    sourceInvoicePrepareId: payload.sourceInvoicePrepareId || '',
    sourceInvoicePrepareNo: payload.sourceInvoicePrepareNo || '',
    sourcePayableCheckNo: payload.sourcePayableCheckNo || '',
    sourcePayablePrepareNo: payload.sourcePayablePrepareNo || '',
    sourceInventoryTransactionIds: payload.sourceInventoryTransactionIds || [],
    sourceInventoryTransactionNos: payload.sourceInventoryTransactionNos || [],
    supplierId: payload.supplierId || '',
    supplierName: payload.supplierName || '',
    buyerId: payload.buyerId || '',
    buyerName: payload.buyerName || '',
    sourcePurchaseOrderNo: payload.sourcePurchaseOrderNo || '',
    sourceReceiveNo: payload.sourceReceiveNo || '',
    sourceInspectionNo: payload.sourceInspectionNo || '',
    rootRequestNo: payload.rootRequestNo || '',
    apStatus: payload.apStatus || 'draft',
    apDate: payload.apDate || today(),
    expectedPayDate: payload.expectedPayDate || '',
    dueDate: payload.dueDate || payload.expectedPayDate || '',
    invoiceType: payload.invoiceType || 'specialVat',
    invoiceNo: payload.invoiceNo || '',
    invoiceDate: payload.invoiceDate || '',
    taxRate: toNumber(payload.taxRate),
    totalNoTaxAmount: roundAmount(payload.totalNoTaxAmount ?? summary.totalNoTaxAmount),
    totalTaxAmount: roundAmount(payload.totalTaxAmount ?? summary.totalTaxAmount),
    totalInvoiceAmount: roundAmount(payload.totalInvoiceAmount ?? summary.totalInvoiceAmount),
    totalPayableAmount,
    paidAmount,
    unpaidAmount: roundAmount(payload.unpaidAmount ?? totalPayableAmount - paidAmount),
    paymentStatus: payload.paymentStatus || 'unpaid',
    voucherStatus: payload.voucherStatus || 'notGenerated',
    paymentReady: payload.paymentReady ?? false,
    voucherReady: payload.voucherReady ?? false,
    paymentDraftGenerated: payload.paymentDraftGenerated ?? false,
    targetPaymentDraftId: payload.targetPaymentDraftId || '',
    targetPaymentDraftNo: payload.targetPaymentDraftNo || '',
    targetModule: payload.targetModule || '',
    paymentDraftGeneratedAt: payload.paymentDraftGeneratedAt || '',
    remark: payload.remark || '',
    lines,
    createdAt: payload.createdAt || stamp,
    updatedAt: payload.updatedAt || stamp,
  }
}

function normalizeState(raw = {}) {
  return { accountPayableDrafts: (raw.accountPayableDrafts || []).map(accountPayableDraft) }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[AP DRAFT STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export function writeApDraftLog(action, payload = {}) {
  addOperationLog({
    module: '采购应付账款草稿',
    action,
    targetType: payload.targetType || 'accountPayableDraft',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源单据：${payload.sourceNo || '-'}`,
      `目标单据：${payload.targetNo || '-'}`,
      `结果：${payload.result || '成功'}`,
    ].join('；'),
  })
}

export function getAccountPayableDraftState() {
  return clone(state)
}

export function saveAccountPayableDraftState(nextState) {
  state = normalizeState(nextState)
  persist()
  writeApDraftLog('保存应付账款草稿状态', { targetType: 'accountPayableDraftState', targetId: 'state' })
  return getAccountPayableDraftState()
}

export function resetAccountPayableDraftState() {
  state = defaultState()
  persist()
  writeApDraftLog('恢复应付账款草稿演示数据', { targetType: 'accountPayableDraftState', targetId: 'demo' })
  return getAccountPayableDraftState()
}

export function listAccountPayableDrafts() {
  return clone(state.accountPayableDrafts)
}

export function getAccountPayableDraftById(id) {
  return clone(byId(state.accountPayableDrafts, id))
}

export function markApDraftPaymentDraftGenerated(id, paymentDraft = {}) {
  const current = byId(state.accountPayableDrafts, id)
  if (!current) return { success: false, error: '未找到应付账款草稿。' }
  Object.assign(current, {
    apStatus: 'paymentPending',
    paymentStatus: 'unpaid',
    paymentReady: true,
    paymentDraftGenerated: true,
    targetPaymentDraftId: paymentDraft.id || paymentDraft.paymentDraftId || current.targetPaymentDraftId || '',
    targetPaymentDraftNo: paymentDraft.paymentDraftNo || current.targetPaymentDraftNo || '',
    targetModule: 'supplierPaymentDraft',
    paymentDraftGeneratedAt: current.paymentDraftGeneratedAt || nowText(),
    updatedAt: nowText(),
  })
  persist()
  writeApDraftLog('生成供应商付款草稿成功后回写应付账款草稿状态', {
    sourceNo: current.apDraftNo,
    targetId: current.targetPaymentDraftId,
    targetNo: current.targetPaymentDraftNo,
  })
  return { success: true, accountPayableDraft: clone(current) }
}

export function isApDraftGenerated(invoicePrepareOrId) {
  const prepare = typeof invoicePrepareOrId === 'object' ? invoicePrepareOrId : getInvoicePrepareById(invoicePrepareOrId)
  if (!prepare?.id) return false
  if (prepare.invoicePrepareStatus === 'apDraftGenerated' || prepare.apDraftGenerated || prepare.targetApDraftId || prepare.targetApDraftNo) return true
  return state.accountPayableDrafts.some((draft) => String(draft.sourceInvoicePrepareId) === String(prepare.id))
}

function sourceRejectReason(prepare = {}) {
  if (!prepare?.id) return '未找到发票预备单。'
  if (isApDraftGenerated(prepare)) {
    writeApDraftLog('拦截重复生成应付账款草稿', {
      sourceNo: prepare.invoicePrepareNo,
      targetId: prepare.targetApDraftId || prepare.id,
      targetNo: prepare.targetApDraftNo || '',
      result: '该发票预备已生成应付账款草稿，不能重复生成。',
    })
    return '该发票预备已生成应付账款草稿，不能重复生成。'
  }
  if (!SOURCE_READY_STATUSES.includes(prepare.invoicePrepareStatus)) return '只有 matched 或 payableReady 状态的发票预备可生成应付账款草稿。'
  if (!toNumber(prepare.totalInvoiceAmount)) return '发票预备含税金额为空，不能生成应付账款草稿。'
  return ''
}

export function getApDraftSourcesFromInvoicePrepares() {
  return listInvoicePrepares().map((prepare) => {
    const generated = isApDraftGenerated(prepare)
    const existed = state.accountPayableDrafts.find((draft) => String(draft.sourceInvoicePrepareId) === String(prepare.id))
    if (generated && existed && !prepare.apDraftGenerated && !prepare.targetApDraftNo) {
      writeApDraftLog('历史数据兼容识别已生成应付账款草稿', {
        sourceNo: prepare.invoicePrepareNo,
        targetId: existed.id,
        targetNo: existed.apDraftNo,
      })
    }
    const reason = sourceRejectReason(prepare)
    return {
      ...prepare,
      invoicePrepareStatus: generated ? 'apDraftGenerated' : prepare.invoicePrepareStatus,
      apDraftGenerated: generated,
      apDraftGeneratedText: generated ? '已生成' : '未生成',
      targetApDraftId: prepare.targetApDraftId || existed?.id || '',
      targetApDraftNo: prepare.targetApDraftNo || existed?.apDraftNo || '',
      canCreateApDraft: !reason,
      sourceRejectReason: reason,
    }
  })
}

function buildLinesFromInvoicePrepare(prepare = {}) {
  return (prepare.lines || []).map((line, index) => normalizeLine({
    ...line,
    lineNo: index + 1,
    payableAmount: line.invoiceAmount,
    sourceInvoicePrepareLineId: line.id,
    sourceInventoryTransactionId: line.sourceInventoryTransactionId || '',
    sourceInventoryTransactionNo: line.sourceInventoryTransactionNo || '',
    sourcePurchaseOrderNo: line.sourcePurchaseOrderNo || prepare.sourcePurchaseOrderNo,
    sourceReceiveNo: line.sourceReceiveNo || prepare.sourceReceiveNo,
    sourceInspectionNo: line.sourceInspectionNo || prepare.sourceInspectionNo,
    rootRequestNo: line.rootRequestNo || prepare.rootRequestNo,
  }, index))
}

export function createApDraftFromInvoicePrepare(invoicePrepareId) {
  const prepare = getInvoicePrepareById(invoicePrepareId)
  const reason = sourceRejectReason(prepare)
  if (reason) {
    writeApDraftLog('应付账款草稿生成拦截', {
      sourceNo: prepare?.invoicePrepareNo || invoicePrepareId,
      targetId: invoicePrepareId,
      result: reason,
    })
    return { success: false, error: reason }
  }
  const lines = buildLinesFromInvoicePrepare(prepare)
  const draft = accountPayableDraft({
    sourceInvoicePrepareId: prepare.id,
    sourceInvoicePrepareNo: prepare.invoicePrepareNo,
    sourcePayableCheckNo: prepare.sourcePayableCheckNo,
    sourcePayablePrepareNo: prepare.sourcePayablePrepareNo,
    sourceInventoryTransactionIds: prepare.sourceInventoryTransactionIds || [],
    sourceInventoryTransactionNos: prepare.sourceInventoryTransactionNos || (prepare.lines || []).map((line) => line.sourceInventoryTransactionNo).filter(Boolean),
    supplierId: prepare.supplierId,
    supplierName: prepare.supplierName,
    buyerId: prepare.buyerId,
    buyerName: prepare.buyerName,
    sourcePurchaseOrderNo: prepare.sourcePurchaseOrderNo,
    sourceReceiveNo: prepare.sourceReceiveNo,
    sourceInspectionNo: prepare.sourceInspectionNo,
    rootRequestNo: prepare.rootRequestNo,
    expectedPayDate: prepare.expectedPayDate || '',
    invoiceType: prepare.invoiceType,
    invoiceNo: prepare.invoiceNo,
    invoiceDate: prepare.invoiceDate,
    taxRate: prepare.taxRate,
    totalNoTaxAmount: prepare.totalNoTaxAmount,
    totalTaxAmount: prepare.totalTaxAmount,
    totalInvoiceAmount: prepare.totalInvoiceAmount,
    totalPayableAmount: prepare.totalInvoiceAmount,
    paidAmount: 0,
    unpaidAmount: prepare.totalInvoiceAmount,
    remark: '由发票预备生成，仅形成应付账款草稿和待付款准备数据，不生成付款单或财务凭证。',
    lines,
  })
  state.accountPayableDrafts.unshift(draft)
  persist()
  const writeBack = markInvoicePrepareApDraftGenerated(prepare.id, draft)
  writeApDraftLog('从发票预备生成应付账款草稿', {
    sourceNo: prepare.invoicePrepareNo,
    targetId: draft.id,
    targetNo: draft.apDraftNo,
    result: draft.totalPayableAmount,
  })
  return { success: true, apDraftId: draft.id, apDraftNo: draft.apDraftNo, accountPayableDraft: clone(draft), writeBackSuccess: Boolean(writeBack?.success) }
}

function batchResult(ids = [], handler, label, noGetter = (id) => id) {
  const result = { total: ids.length, successCount: 0, failedCount: 0, successItems: [], failedItems: [], failedReason: [] }
  ids.forEach((id) => {
    const no = noGetter(id)
    const outcome = handler(id)
    if (outcome?.success) {
      result.successCount += 1
      result.successItems.push({ id, no, writeBackSuccess: Boolean(outcome.writeBackSuccess) })
      return
    }
    const reason = outcome?.error || '当前记录不满足批量操作条件。'
    result.failedCount += 1
    result.failedItems.push({ id, no, reason })
    result.failedReason.push(`${no}：${reason}`)
  })
  const writeBackCount = result.successItems.filter((item) => item.writeBackSuccess).length
  result.writeBackCount = writeBackCount
  writeApDraftLog(label, { targetType: 'batch', targetId: label, result: `成功 ${result.successCount} 条，已回写 ${writeBackCount} 条，失败 ${result.failedCount} 条；${result.failedReason.join('；')}` })
  if (result.failedCount) writeApDraftLog('批量失败原因', { targetType: 'batch', targetId: label, result: result.failedReason.join('；') })
  return result
}

export function batchCreateApDraftsFromInvoicePrepares(ids = []) {
  return batchResult(ids, createApDraftFromInvoicePrepare, '批量生成应付账款草稿', (id) => getInvoicePrepareById(id)?.invoicePrepareNo || id)
}

export function updateApDraft(id, patch = {}) {
  const current = byId(state.accountPayableDrafts, id)
  if (!current || ['cancelled', 'closed', 'paymentPending'].includes(current.apStatus)) return { success: false, error: '当前应付账款草稿不可修改。' }
  Object.assign(current, accountPayableDraft({ ...current, ...patch, id: current.id, updatedAt: nowText() }))
  persist()
  writeApDraftLog('更新应付账款草稿', { targetId: current.id, targetNo: current.apDraftNo })
  return { success: true, accountPayableDraft: clone(current) }
}

function markStatus(id, status, action, patch = {}) {
  const current = byId(state.accountPayableDrafts, id)
  if (!current) return { success: false, error: '未找到应付账款草稿。' }
  if (['cancelled', 'closed'].includes(current.apStatus)) return { success: false, error: '已取消或已关闭的应付账款草稿不能继续流转。' }
  if (current.apStatus === 'paymentPending' && status !== 'paymentPending') return { success: false, error: '已进入待付款准备，本轮不允许回退或继续付款。' }
  Object.assign(current, patch, { apStatus: status, updatedAt: nowText() })
  if (status === 'paymentPending') {
    current.paymentReady = true
    current.paymentStatus = 'unpaid'
  }
  persist()
  writeApDraftLog(action, { targetId: current.id, targetNo: current.apDraftNo })
  return { success: true, accountPayableDraft: clone(current) }
}

export function markApDraftConfirmed(id) {
  const current = byId(state.accountPayableDrafts, id)
  if (current && current.apStatus !== 'draft') return { success: false, error: '只有草稿状态可确认应付草稿。' }
  return markStatus(id, 'confirmed', '确认应付草稿')
}

export function markApDraftPaymentPending(id) {
  const current = byId(state.accountPayableDrafts, id)
  if (current && current.apStatus !== 'confirmed') return { success: false, error: '只有已确认状态可标记待付款。' }
  return markStatus(id, 'paymentPending', '标记待付款')
}

export function cancelApDraft(id) {
  const current = byId(state.accountPayableDrafts, id)
  if (current && !['draft', 'confirmed'].includes(current.apStatus)) return { success: false, error: '只有草稿或已确认状态可取消。' }
  return markStatus(id, 'cancelled', '取消应付草稿')
}

export function batchMarkApDraftConfirmed(ids = []) {
  return batchResult(ids, markApDraftConfirmed, '批量确认应付草稿', (id) => byId(state.accountPayableDrafts, id)?.apDraftNo || id)
}

export function batchMarkApDraftPaymentPending(ids = []) {
  return batchResult(ids, markApDraftPaymentPending, '批量标记待付款', (id) => byId(state.accountPayableDrafts, id)?.apDraftNo || id)
}

export function batchCancelApDrafts(ids = []) {
  return batchResult(ids, cancelApDraft, '批量取消应付草稿', (id) => byId(state.accountPayableDrafts, id)?.apDraftNo || id)
}
