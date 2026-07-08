import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  getPayableCheckById,
  listPayableChecks,
  markPayableCheckInvoicePrepared,
} from './payableCheckStore.js'

const STORAGE_KEY = 'invoice-prepare-state-v1'
const SOURCE_READY_STATUSES = ['checked', 'invoicePrepareReady']
const DEFAULT_TAX_RATE = 13

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
  return { invoicePrepares: [] }
}

function byId(collection, id) {
  return (collection || []).find((item) => String(item.id) === String(id)) || null
}

function splitTax(invoiceAmount, taxRate = DEFAULT_TAX_RATE) {
  const amount = roundAmount(invoiceAmount)
  const rate = toNumber(taxRate) / 100
  const noTaxAmount = roundAmount(rate > 0 ? amount / (1 + rate) : amount)
  const taxAmount = roundAmount(amount - noTaxAmount)
  return { noTaxAmount, taxAmount, invoiceAmount: amount }
}

function normalizeLine(line = {}, index = 0, taxRate = DEFAULT_TAX_RATE) {
  const checkedQty = toNumber(line.checkedQty)
  const checkedPrice = toNumber(line.checkedPrice)
  const checkedAmount = roundAmount(line.checkedAmount || checkedQty * checkedPrice)
  const split = splitTax(line.invoiceAmount ?? checkedAmount, line.taxRate ?? taxRate)
  return {
    id: line.id || createId('ipl'),
    lineNo: line.lineNo || index + 1,
    materialId: line.materialId || '',
    materialCode: line.materialCode || '',
    materialName: line.materialName || '',
    spec: line.spec || line.specification || '',
    unit: line.unit || '',
    checkedQty,
    checkedPrice,
    checkedAmount,
    noTaxAmount: roundAmount(line.noTaxAmount ?? split.noTaxAmount),
    taxRate: toNumber(line.taxRate ?? taxRate),
    taxAmount: roundAmount(line.taxAmount ?? split.taxAmount),
    invoiceAmount: roundAmount(line.invoiceAmount ?? split.invoiceAmount),
    sourcePayableCheckLineId: line.sourcePayableCheckLineId || line.id || '',
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
  return {
    totalNoTaxAmount: roundAmount(lines.reduce((sum, line) => sum + toNumber(line.noTaxAmount), 0)),
    totalTaxAmount: roundAmount(lines.reduce((sum, line) => sum + toNumber(line.taxAmount), 0)),
    totalInvoiceAmount: roundAmount(lines.reduce((sum, line) => sum + toNumber(line.invoiceAmount), 0)),
  }
}

function invoicePrepare(payload = {}) {
  const stamp = nowText()
  const taxRate = toNumber(payload.taxRate ?? DEFAULT_TAX_RATE)
  const lines = (payload.lines || []).map((line, index) => normalizeLine(line, index, taxRate))
  const summary = summarizeLines(lines)
  return {
    id: payload.id || createId('ip'),
    invoicePrepareNo: payload.invoicePrepareNo || createNo('IP'),
    sourcePayableCheckId: payload.sourcePayableCheckId || '',
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
    invoicePrepareStatus: payload.invoicePrepareStatus || 'prepared',
    expectedInvoiceDate: payload.expectedInvoiceDate || today(),
    invoiceType: payload.invoiceType || 'specialVat',
    taxRate,
    totalNoTaxAmount: roundAmount(payload.totalNoTaxAmount ?? summary.totalNoTaxAmount),
    totalTaxAmount: roundAmount(payload.totalTaxAmount ?? summary.totalTaxAmount),
    totalInvoiceAmount: roundAmount(payload.totalInvoiceAmount ?? summary.totalInvoiceAmount),
    invoiceNo: payload.invoiceNo || '',
    invoiceDate: payload.invoiceDate || '',
    invoiceReceived: payload.invoiceReceived ?? false,
    invoiceReceivedDate: payload.invoiceReceivedDate || '',
    invoiceMatchStatus: payload.invoiceMatchStatus || 'unmatched',
    differenceReason: payload.differenceReason || '',
    apDraftGenerated: payload.apDraftGenerated ?? false,
    targetApDraftId: payload.targetApDraftId || '',
    targetApDraftNo: payload.targetApDraftNo || '',
    targetModule: payload.targetModule || '',
    apDraftGeneratedAt: payload.apDraftGeneratedAt || '',
    remark: payload.remark || '',
    lines,
    createdAt: payload.createdAt || stamp,
    updatedAt: payload.updatedAt || stamp,
  }
}

function normalizeState(raw = {}) {
  return { invoicePrepares: (raw.invoicePrepares || []).map(invoicePrepare) }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[INVOICE PREPARE STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export function writeInvoicePrepareLog(action, payload = {}) {
  addOperationLog({
    module: '采购发票预备',
    action,
    targetType: payload.targetType || 'invoicePrepare',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源单据：${payload.sourceNo || '-'}`,
      `目标单据：${payload.targetNo || '-'}`,
      `结果：${payload.result || '成功'}`,
    ].join('；'),
  })
}

export function getInvoicePrepareState() {
  return clone(state)
}

export function saveInvoicePrepareState(nextState) {
  state = normalizeState(nextState)
  persist()
  writeInvoicePrepareLog('保存发票预备状态', { targetType: 'invoicePrepareState', targetId: 'state' })
  return getInvoicePrepareState()
}

export function resetInvoicePrepareState() {
  state = defaultState()
  persist()
  writeInvoicePrepareLog('恢复发票预备演示数据', { targetType: 'invoicePrepareState', targetId: 'demo' })
  return getInvoicePrepareState()
}

export function listInvoicePrepares() {
  return clone(state.invoicePrepares)
}

export function getInvoicePrepareById(id) {
  return clone(byId(state.invoicePrepares, id))
}

export function markInvoicePrepareApDraftGenerated(id, apDraft = {}) {
  const current = byId(state.invoicePrepares, id)
  if (!current) return { success: false, error: '未找到发票预备单。' }
  Object.assign(current, {
    invoicePrepareStatus: 'apDraftGenerated',
    apDraftGenerated: true,
    targetApDraftId: apDraft.id || apDraft.apDraftId || current.targetApDraftId || '',
    targetApDraftNo: apDraft.apDraftNo || current.targetApDraftNo || '',
    targetModule: 'accountPayableDraft',
    apDraftGeneratedAt: current.apDraftGeneratedAt || nowText(),
    updatedAt: nowText(),
  })
  persist()
  writeInvoicePrepareLog('生成应付账款草稿成功后回写发票预备状态', {
    sourceNo: current.invoicePrepareNo,
    targetId: current.targetApDraftId,
    targetNo: current.targetApDraftNo,
  })
  return { success: true, invoicePrepare: clone(current) }
}

export function isInvoicePrepareGenerated(payableCheckOrId) {
  const check = typeof payableCheckOrId === 'object' ? payableCheckOrId : getPayableCheckById(payableCheckOrId)
  if (!check?.id) return false
  return state.invoicePrepares.some((prepare) => String(prepare.sourcePayableCheckId) === String(check.id))
}

function sourceRejectReason(check = {}) {
  if (!check?.id) return '未找到应付核对单。'
  if (check.checkStatus === 'invoicePrepared' || check.invoicePrepareGenerated || check.targetInvoicePrepareId || check.targetInvoicePrepareNo || isInvoicePrepareGenerated(check)) {
    return '该应付核对已生成发票预备，不能重复生成。'
  }
  if (check.checkStatus === 'difference') return '存在差异的应付核对不能直接生成发票预备。'
  if (['pending', 'processing'].includes(check.differenceStatus) || (check.differenceStatus && check.differenceStatus !== 'none' && check.differenceResolved !== true)) return '差异尚未处理，不能生成发票预备。'
  if (!SOURCE_READY_STATUSES.includes(check.checkStatus)) return '当前应付核对未达到 checked 或 invoicePrepareReady，不能生成发票预备。'
  if (!toNumber(check.totalCheckedAmount)) return '应付核对金额为空，不能生成发票预备。'
  return ''
}

export function getInvoicePrepareSourcesFromPayableChecks() {
  return listPayableChecks().map((check) => {
    const generated = isInvoicePrepareGenerated(check)
    const reason = sourceRejectReason(check)
    return {
      ...check,
      invoicePrepareGenerated: generated,
      invoicePrepareGeneratedText: generated ? '已生成' : '未生成',
      canCreateInvoicePrepare: !reason,
      sourceRejectReason: reason,
    }
  })
}

function buildLinesFromCheck(check = {}, taxRate = DEFAULT_TAX_RATE) {
  return (check.lines || []).map((line, index) => normalizeLine({
    ...line,
    lineNo: index + 1,
    sourcePayableCheckLineId: line.id,
    sourceInventoryTransactionId: line.sourceInventoryTransactionId || '',
    sourceInventoryTransactionNo: line.sourceInventoryTransactionNo || '',
    sourceReceiveNo: line.sourceReceiveNo || check.sourceReceiveNo,
    sourceInspectionNo: line.sourceInspectionNo || check.sourceInspectionNo,
    sourcePurchaseOrderNo: line.sourcePurchaseOrderNo || check.sourcePurchaseOrderNo,
    rootRequestNo: line.rootRequestNo || check.rootRequestNo,
  }, index, taxRate))
}

export function createInvoicePrepareFromPayableCheck(payableCheckId) {
  const check = getPayableCheckById(payableCheckId)
  const reason = sourceRejectReason(check)
  if (reason) {
    writeInvoicePrepareLog('发票预备生成拦截', {
      sourceNo: check?.payableCheckNo || payableCheckId,
      targetId: payableCheckId,
      result: reason,
    })
    return { success: false, error: reason }
  }
  const lines = buildLinesFromCheck(check, DEFAULT_TAX_RATE)
  const summary = summarizeLines(lines)
  const prepare = invoicePrepare({
    sourcePayableCheckId: check.id,
    sourcePayableCheckNo: check.payableCheckNo,
    sourcePayablePrepareNo: check.sourcePayablePrepareNo,
    sourceInventoryTransactionIds: check.sourceInventoryTransactionIds || [],
    sourceInventoryTransactionNos: check.sourceInventoryTransactionNos || (check.lines || []).map((line) => line.sourceInventoryTransactionNo).filter(Boolean),
    supplierId: check.supplierId,
    supplierName: check.supplierName,
    buyerId: check.buyerId,
    buyerName: check.buyerName,
    sourcePurchaseOrderNo: check.sourcePurchaseOrderNo,
    sourceReceiveNo: check.sourceReceiveNo,
    sourceInspectionNo: check.sourceInspectionNo,
    rootRequestNo: check.rootRequestNo,
    totalNoTaxAmount: summary.totalNoTaxAmount,
    totalTaxAmount: summary.totalTaxAmount,
    totalInvoiceAmount: summary.totalInvoiceAmount,
    remark: '由应付核对生成，仅用于发票信息预登记和匹配准备。',
    lines,
  })
  state.invoicePrepares.unshift(prepare)
  persist()
  const writeBack = markPayableCheckInvoicePrepared(check.id, prepare)
  writeInvoicePrepareLog('从应付核对生成发票预备', {
    sourceNo: check.payableCheckNo,
    targetId: prepare.id,
    targetNo: prepare.invoicePrepareNo,
    result: prepare.totalInvoiceAmount,
  })
  return { success: true, invoicePrepareId: prepare.id, invoicePrepareNo: prepare.invoicePrepareNo, invoicePrepare: clone(prepare), writeBackSuccess: Boolean(writeBack?.success) }
}

function batchResult(ids = [], handler, label, noGetter = (id) => id) {
  const result = { total: ids.length, successCount: 0, failedCount: 0, successItems: [], failedItems: [], failedReason: [] }
  ids.forEach((id) => {
    const no = noGetter(id)
    const outcome = handler(id)
    if (outcome?.success) {
      result.successCount += 1
      result.successItems.push({ id, no, writeBackSuccess: Boolean(outcome.writeBackSuccess) })
    } else {
      const reason = outcome?.error || '当前记录不满足批量操作条件。'
      result.failedCount += 1
      result.failedItems.push({ id, no, reason })
      result.failedReason.push(`${no}：${reason}`)
    }
  })
  const writeBackCount = result.successItems.filter((item) => item.writeBackSuccess).length
  result.writeBackCount = writeBackCount
  writeInvoicePrepareLog(label, { targetType: 'batch', targetId: label, result: `成功 ${result.successCount} 条，已回写 ${writeBackCount} 条，失败 ${result.failedCount} 条；${result.failedReason.join('；')}` })
  if (result.failedCount) writeInvoicePrepareLog('批量失败原因', { targetType: 'batch', targetId: label, result: result.failedReason.join('；') })
  return result
}

export function batchCreateInvoicePreparesFromPayableChecks(ids = []) {
  return batchResult(ids, createInvoicePrepareFromPayableCheck, '批量生成发票预备', (id) => getPayableCheckById(id)?.payableCheckNo || id)
}

export function updateInvoicePrepare(id, patch = {}) {
  const current = byId(state.invoicePrepares, id)
  if (!current || ['cancelled', 'closed', 'payableReady'].includes(current.invoicePrepareStatus)) return { success: false, error: '当前发票预备不可修改。' }
  Object.assign(current, invoicePrepare({ ...current, ...patch, id: current.id, updatedAt: nowText() }))
  persist()
  writeInvoicePrepareLog('更新发票预备', { targetId: current.id, targetNo: current.invoicePrepareNo })
  return { success: true, invoicePrepare: clone(current) }
}

function markStatus(id, status, action, patch = {}) {
  const current = byId(state.invoicePrepares, id)
  if (!current) return { success: false, error: '未找到发票预备单。' }
  if (['cancelled', 'closed'].includes(current.invoicePrepareStatus)) return { success: false, error: '已取消或已关闭的发票预备不能继续流转。' }
  Object.assign(current, patch, { invoicePrepareStatus: status, updatedAt: nowText() })
  if (status === 'invoiceReceived') {
    current.invoiceReceived = true
    current.invoiceReceivedDate = current.invoiceReceivedDate || today()
  }
  if (status === 'matched') current.invoiceMatchStatus = 'matched'
  if (status === 'difference') current.invoiceMatchStatus = 'difference'
  persist()
  writeInvoicePrepareLog(action, { targetId: current.id, targetNo: current.invoicePrepareNo })
  return { success: true, invoicePrepare: clone(current) }
}

export function markWaitingInvoice(id) {
  return markStatus(id, 'waitingInvoice', '标记待收票')
}

export function markInvoiceReceived(id) {
  return markStatus(id, 'invoiceReceived', '标记已收票')
}

export function markInvoiceMatched(id) {
  return markStatus(id, 'matched', '标记发票已匹配')
}

export function markInvoiceDifference(id, reason = '发票金额或来源存在差异') {
  return markStatus(id, 'difference', '标记发票差异', { differenceReason: reason })
}

export function markPayableReady(id) {
  return markStatus(id, 'payableReady', '标记可进入正式应付')
}

export function cancelInvoicePrepare(id) {
  return markStatus(id, 'cancelled', '取消发票预备')
}

export function batchMarkWaitingInvoice(ids = []) {
  return batchResult(ids, markWaitingInvoice, '批量标记待收票', (id) => byId(state.invoicePrepares, id)?.invoicePrepareNo || id)
}

export function batchMarkInvoiceReceived(ids = []) {
  return batchResult(ids, markInvoiceReceived, '批量标记已收票', (id) => byId(state.invoicePrepares, id)?.invoicePrepareNo || id)
}

export function batchMarkInvoiceMatched(ids = []) {
  return batchResult(ids, markInvoiceMatched, '批量标记已匹配', (id) => byId(state.invoicePrepares, id)?.invoicePrepareNo || id)
}

export function batchMarkPayableReady(ids = []) {
  return batchResult(ids, markPayableReady, '批量标记可进入正式应付', (id) => byId(state.invoicePrepares, id)?.invoicePrepareNo || id)
}
