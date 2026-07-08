import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import { listPayablePrepares, getPayablePrepareById } from './payablePrepareStore.js'

const STORAGE_KEY = 'payable-check-state-v1'
const SOURCE_READY_STATUSES = ['payableReady', 'checked']
const DIFFERENCE_BLOCKED_MESSAGE = '差异尚未处理，不能生成发票预备。'

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
  return { payableChecks: [] }
}

function byId(collection, id) {
  return (collection || []).find((item) => String(item.id) === String(id)) || null
}

function normalizeLine(line = {}, index = 0) {
  const payableQty = toNumber(line.payableQty)
  const payablePrice = toNumber(line.payablePrice)
  const payableAmount = roundAmount(line.payableAmount || payableQty * payablePrice)
  const checkedQty = toNumber(line.checkedQty ?? payableQty)
  const checkedPrice = toNumber(line.checkedPrice ?? payablePrice)
  const checkedAmount = roundAmount(line.checkedAmount ?? checkedQty * checkedPrice)
  return {
    id: line.id || createId('pcl'),
    lineNo: line.lineNo || index + 1,
    materialId: line.materialId || '',
    materialCode: line.materialCode || '',
    materialName: line.materialName || '',
    spec: line.spec || line.specification || '',
    unit: line.unit || '',
    batchNo: line.batchNo || '',
    warehouseName: line.warehouseName || '',
    locationName: line.locationName || '',
    qualityStatus: line.qualityStatus || '',
    payableQty,
    payablePrice,
    payableAmount,
    checkedQty,
    checkedPrice,
    checkedAmount,
    quantityDifference: toNumber(line.quantityDifference ?? checkedQty - payableQty),
    priceDifference: roundAmount(line.priceDifference ?? checkedPrice - payablePrice),
    amountDifference: roundAmount(line.amountDifference ?? checkedAmount - payableAmount),
    differenceType: line.differenceType || '',
    differenceReason: line.differenceReason || '',
    differenceResolution: line.differenceResolution || '',
    differenceResolved: Boolean(line.differenceResolved),
    sourcePayablePrepareLineId: line.sourcePayablePrepareLineId || line.id || '',
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
  const totalPayableQty = lines.reduce((sum, line) => sum + toNumber(line.payableQty), 0)
  const totalPayableAmount = roundAmount(lines.reduce((sum, line) => sum + toNumber(line.payableAmount), 0))
  const totalCheckedQty = lines.reduce((sum, line) => sum + toNumber(line.checkedQty), 0)
  const totalCheckedAmount = roundAmount(lines.reduce((sum, line) => sum + toNumber(line.checkedAmount), 0))
  return {
    totalPayableQty,
    totalPayableAmount,
    totalCheckedQty,
    totalCheckedAmount,
    quantityDifference: toNumber(totalCheckedQty - totalPayableQty),
    amountDifference: roundAmount(totalCheckedAmount - totalPayableAmount),
  }
}

function payableCheck(payload = {}) {
  const stamp = nowText()
  const lines = (payload.lines || []).map(normalizeLine)
  const summary = summarizeLines(lines)
  const amountDifference = roundAmount(payload.amountDifference ?? summary.amountDifference)
  const quantityDifference = toNumber(payload.quantityDifference ?? summary.quantityDifference)
  const hasDifference = payload.checkStatus === 'difference' || Boolean(amountDifference || quantityDifference || payload.differenceReason)
  const differenceResolved = Boolean(payload.differenceResolved)
  const differenceStatus = payload.differenceStatus || (hasDifference ? (differenceResolved ? 'resolved' : 'pending') : 'none')
  const rawCheckStatus = payload.checkStatus || 'draft'
  const checkStatus = normalizePayableCheckStatus({
    checkStatus: rawCheckStatus,
    differenceStatus,
    differenceResolved,
    recheckRequired: payload.recheckRequired ?? false,
  })
  return {
    id: payload.id || createId('pc'),
    payableCheckNo: payload.payableCheckNo || createNo('PC'),
    sourcePayablePrepareId: payload.sourcePayablePrepareId || '',
    sourcePayablePrepareNo: payload.sourcePayablePrepareNo || '',
    sourceInventoryTransactionIds: payload.sourceInventoryTransactionIds || [],
    sourceInventoryTransactionNos: payload.sourceInventoryTransactionNos || [],
    sourceInspectionNo: payload.sourceInspectionNo || '',
    sourceReceiveNo: payload.sourceReceiveNo || '',
    sourcePurchaseOrderNo: payload.sourcePurchaseOrderNo || '',
    rootRequestNo: payload.rootRequestNo || '',
    supplierId: payload.supplierId || '',
    supplierName: payload.supplierName || '',
    buyerId: payload.buyerId || '',
    buyerName: payload.buyerName || '',
    requestDepartment: payload.requestDepartment || '',
    demandDepartment: payload.demandDepartment || '',
    purchaseDepartment: payload.purchaseDepartment || '',
    checkStatus,
    checkDate: payload.checkDate || today(),
    checkerId: payload.checkerId || '',
    checkerName: payload.checkerName || '',
    totalPayableQty: toNumber(payload.totalPayableQty ?? summary.totalPayableQty),
    totalPayableAmount: roundAmount(payload.totalPayableAmount ?? summary.totalPayableAmount),
    totalCheckedQty: toNumber(payload.totalCheckedQty ?? summary.totalCheckedQty),
    totalCheckedAmount: roundAmount(payload.totalCheckedAmount ?? summary.totalCheckedAmount),
    amountDifference,
    quantityDifference,
    checkResult: payload.checkResult || (amountDifference || quantityDifference ? 'difference' : 'matched'),
    differenceStatus,
    differenceType: payload.differenceType || '',
    differenceReason: payload.differenceReason || '',
    differenceHandlerId: payload.differenceHandlerId || '',
    differenceHandlerName: payload.differenceHandlerName || '',
    differenceHandledAt: payload.differenceHandledAt || '',
    differenceResolution: payload.differenceResolution || '',
    differenceResolved,
    recheckRequired: payload.recheckRequired ?? false,
    recheckedAt: payload.recheckedAt || '',
    recheckResult: payload.recheckResult || '',
    adjustmentRequired: payload.adjustmentRequired ?? Boolean(amountDifference || quantityDifference),
    invoicePrepareReady: checkStatus === 'difference' ? false : (payload.invoicePrepareReady ?? false),
    invoicePrepareGenerated: payload.invoicePrepareGenerated ?? false,
    targetInvoicePrepareId: payload.targetInvoicePrepareId || '',
    targetInvoicePrepareNo: payload.targetInvoicePrepareNo || '',
    targetModule: payload.targetModule || '',
    invoicePreparedAt: payload.invoicePreparedAt || '',
    remark: payload.remark || '',
    lines,
    createdAt: payload.createdAt || stamp,
    updatedAt: payload.updatedAt || stamp,
  }
}

function normalizePayableCheckStatus(record = {}) {
  const checkStatus = record.checkStatus || 'draft'
  const differenceStatus = record.differenceStatus || 'none'
  if (['pending', 'processing'].includes(differenceStatus) && ['checked', 'invoicePrepared', 'invoicePrepareReady'].includes(checkStatus)) return 'difference'
  if (checkStatus === 'checked' && record.recheckRequired === true) return record.differenceResolved ? 'difference' : checkStatus
  return checkStatus
}

function normalizeCurrentStatus(current) {
  if (!current) return
  const nextStatus = normalizePayableCheckStatus(current)
  if (nextStatus !== current.checkStatus) {
    current.checkStatus = nextStatus
    current.invoicePrepareReady = false
    writePayableCheckLog('发现应付核对状态不一致并规范化显示', {
      targetId: current.id,
      targetNo: current.payableCheckNo,
      result: `规范为 ${nextStatus} / ${current.differenceStatus || 'none'}`,
    })
  }
}

function normalizeState(raw = {}) {
  return { payableChecks: (raw.payableChecks || []).map(payableCheck) }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[PAYABLE CHECK STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export function writePayableCheckLog(action, payload = {}) {
  addOperationLog({
    module: '采购应付核对',
    action,
    targetType: payload.targetType || 'payableCheck',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源单据：${payload.sourceNo || '-'}`,
      `目标单据：${payload.targetNo || '-'}`,
      `结果：${payload.result || '成功'}`,
    ].join('；'),
  })
}

export function getPayableCheckState() {
  return clone(state)
}

export function savePayableCheckState(nextState) {
  state = normalizeState(nextState)
  persist()
  writePayableCheckLog('保存应付核对状态', { targetType: 'payableCheckState', targetId: 'state' })
  return getPayableCheckState()
}

export function resetPayableCheckState() {
  state = defaultState()
  persist()
  writePayableCheckLog('恢复应付核对演示数据', { targetType: 'payableCheckState', targetId: 'demo' })
  return getPayableCheckState()
}

export function listPayableChecks() {
  return clone(state.payableChecks)
}

export function getPayableCheckById(id) {
  return clone(byId(state.payableChecks, id))
}

export function isPayableCheckGenerated(payablePrepareOrId) {
  const prepare = typeof payablePrepareOrId === 'object' ? payablePrepareOrId : getPayablePrepareById(payablePrepareOrId)
  if (!prepare?.id) return false
  return state.payableChecks.some((check) => String(check.sourcePayablePrepareId) === String(prepare.id))
}

function sourceRejectReason(prepare = {}) {
  if (!prepare?.id) return '未找到应付预备单。'
  if (!SOURCE_READY_STATUSES.includes(prepare.payableStatus)) return '当前应付预备未达到 payableReady 或 checked，不能生成应付核对。'
  if (isPayableCheckGenerated(prepare)) return '该应付预备已生成应付核对，不能重复生成。'
  if (!toNumber(prepare.totalPayableQty) || !toNumber(prepare.totalPayableAmount)) return '应付预备数量或金额为空，不能生成应付核对。'
  return ''
}

export function getPayableCheckSourcesFromPayablePrepares() {
  return listPayablePrepares().map((prepare) => {
    const generated = isPayableCheckGenerated(prepare)
    const reason = sourceRejectReason(prepare)
    return {
      ...prepare,
      payableCheckGenerated: generated,
      payableCheckGeneratedText: generated ? '已生成' : '未生成',
      canCreatePayableCheck: !reason,
      sourceRejectReason: reason,
    }
  })
}

function buildLinesFromPrepare(prepare = {}) {
  return (prepare.lines || []).map((line, index) => normalizeLine({
    ...line,
    lineNo: index + 1,
    sourcePayablePrepareLineId: line.id,
    sourceInventoryTransactionId: line.sourceInventoryTransactionId || '',
    sourceInventoryTransactionNo: line.sourceInventoryTransactionNo || '',
    sourceReceiveNo: prepare.sourceReceiveNo,
    sourceInspectionNo: prepare.sourceInspectionNo,
    sourcePurchaseOrderNo: line.sourcePurchaseOrderNo || prepare.sourcePurchaseOrderNo,
    rootRequestNo: line.rootRequestNo || prepare.rootRequestNo,
  }))
}

export function createPayableCheckFromPayablePrepare(payablePrepareId) {
  const prepare = getPayablePrepareById(payablePrepareId)
  const reason = sourceRejectReason(prepare)
  if (reason) {
    writePayableCheckLog('应付核对生成拦截', {
      sourceNo: prepare?.payablePrepareNo || payablePrepareId,
      targetId: payablePrepareId,
      result: reason,
    })
    return { success: false, error: reason }
  }
  const lines = buildLinesFromPrepare(prepare)
  const summary = summarizeLines(lines)
  const check = payableCheck({
    sourcePayablePrepareId: prepare.id,
    sourcePayablePrepareNo: prepare.payablePrepareNo,
    sourceInventoryTransactionIds: prepare.sourceInventoryTransactionIds || [],
    sourceInventoryTransactionNos: prepare.sourceInventoryTransactionNos || (prepare.lines || []).map((line) => line.sourceInventoryTransactionNo).filter(Boolean),
    sourceInspectionNo: prepare.sourceInspectionNo,
    sourceReceiveNo: prepare.sourceReceiveNo,
    sourcePurchaseOrderNo: prepare.sourcePurchaseOrderNo,
    rootRequestNo: prepare.rootRequestNo,
    supplierId: prepare.supplierId,
    supplierName: prepare.supplierName,
    buyerId: prepare.buyerId,
    buyerName: prepare.buyerName,
    requestDepartment: prepare.requestDepartment,
    demandDepartment: prepare.demandDepartment,
    purchaseDepartment: prepare.purchaseDepartment,
    totalPayableQty: summary.totalPayableQty,
    totalPayableAmount: summary.totalPayableAmount,
    totalCheckedQty: summary.totalCheckedQty,
    totalCheckedAmount: summary.totalCheckedAmount,
    quantityDifference: summary.quantityDifference,
    amountDifference: summary.amountDifference,
    remark: '由应付预备生成，仅用于数量、单价、金额和来源链核对。',
    lines,
  })
  state.payableChecks.unshift(check)
  persist()
  writePayableCheckLog('从应付预备生成应付核对', {
    sourceNo: prepare.payablePrepareNo,
    targetId: check.id,
    targetNo: check.payableCheckNo,
    result: check.totalCheckedAmount,
  })
  return { success: true, payableCheckId: check.id, payableCheckNo: check.payableCheckNo, payableCheck: clone(check) }
}

function batchResult(ids = [], handler, label, noGetter = (id) => id) {
  const result = { total: ids.length, successCount: 0, failedCount: 0, successItems: [], failedItems: [], failedReason: [] }
  ids.forEach((id) => {
    const no = noGetter(id)
    const outcome = handler(id)
    if (outcome?.success) {
      result.successCount += 1
      result.successItems.push({ id, no })
    } else {
      const reason = outcome?.error || '当前记录不满足批量操作条件。'
      result.failedCount += 1
      result.failedItems.push({ id, no, reason })
      result.failedReason.push(`${no}：${reason}`)
    }
  })
  writePayableCheckLog(label, { targetType: 'batch', targetId: label, result: `成功 ${result.successCount} 条，失败 ${result.failedCount} 条；${result.failedReason.join('；')}` })
  if (result.failedCount) writePayableCheckLog('批量失败原因', { targetType: 'batch', targetId: label, result: result.failedReason.join('；') })
  return result
}

export function batchCreatePayableChecksFromPayablePrepares(ids = []) {
  return batchResult(ids, createPayableCheckFromPayablePrepare, '批量生成应付核对', (id) => getPayablePrepareById(id)?.payablePrepareNo || id)
}

export function updatePayableCheck(id, patch = {}) {
  const current = byId(state.payableChecks, id)
  if (!current || ['cancelled', 'closed', 'invoicePrepared'].includes(current.checkStatus)) return { success: false, error: '当前应付核对不可修改。' }
  Object.assign(current, payableCheck({ ...current, ...patch, id: current.id, updatedAt: nowText() }))
  persist()
  writePayableCheckLog('更新应付核对', { targetId: current.id, targetNo: current.payableCheckNo })
  return { success: true, payableCheck: clone(current) }
}

function markStatus(id, status, action, patch = {}) {
  const current = byId(state.payableChecks, id)
  if (!current) return { success: false, error: '未找到应付核对单。' }
  normalizeCurrentStatus(current)
  if (['cancelled', 'closed', 'invoicePrepared'].includes(current.checkStatus)) return { success: false, error: '已取消、已关闭或已生成发票预备的应付核对不能继续流转。' }
  if (status === 'checked' && current.checkStatus === 'difference' && current.differenceResolved !== true) {
    writePayableCheckLog('差异未处理时拦截核对通过', { targetId: current.id, targetNo: current.payableCheckNo, result: '差异尚未处理，不能核对通过。' })
    return { success: false, error: '差异尚未处理，不能核对通过。' }
  }
  if (status === 'invoicePrepareReady' && isDifferenceBlocked(current)) {
    writePayableCheckLog('差异未处理时拦截生成发票预备', { targetId: current.id, targetNo: current.payableCheckNo, result: DIFFERENCE_BLOCKED_MESSAGE })
    return { success: false, error: DIFFERENCE_BLOCKED_MESSAGE }
  }
  Object.assign(current, patch, { checkStatus: status, updatedAt: nowText() })
  if (status === 'checked') {
    current.checkResult = current.amountDifference || current.quantityDifference ? 'difference' : 'matched'
    current.adjustmentRequired = Boolean(current.amountDifference || current.quantityDifference)
    current.recheckRequired = false
    if (current.differenceResolved) current.recheckResult = 'passed'
  }
  if (status === 'difference') {
    current.checkResult = 'difference'
    current.adjustmentRequired = true
    current.invoicePrepareReady = false
    current.differenceStatus = current.differenceResolved ? 'resolved' : 'pending'
  }
  if (status === 'invoicePrepareReady') current.invoicePrepareReady = true
  persist()
  writePayableCheckLog(action, { targetId: current.id, targetNo: current.payableCheckNo })
  return { success: true, payableCheck: clone(current) }
}

export function markPayableCheckChecking(id) {
  return markStatus(id, 'checking', '标记应付核对中')
}

export function markPayableCheckChecked(id) {
  return markStatus(id, 'checked', '标记应付已核对')
}

export function markPayableCheckDifference(id, reason = '存在数量或金额差异') {
  return markStatus(id, 'difference', '标记差异', {
    differenceStatus: 'pending',
    differenceResolved: false,
    recheckRequired: false,
    differenceReason: reason,
  })
}

export function markInvoicePrepareReady(id) {
  return markStatus(id, 'invoicePrepareReady', '标记可生成发票预备')
}

function isDifferenceBlocked(check = {}) {
  return check.checkStatus === 'difference'
    || ['pending', 'processing'].includes(check.differenceStatus)
    || (check.differenceStatus && check.differenceStatus !== 'none' && check.differenceResolved !== true)
}

export function startPayableCheckDifferenceHandling(id) {
  const current = byId(state.payableChecks, id)
  if (!current) return { success: false, error: '未找到应付核对单。' }
  normalizeCurrentStatus(current)
  if (current.checkStatus !== 'difference') return { success: false, error: '只有存在差异的应付核对需要处理差异。' }
  if (current.differenceStatus === 'resolved') return { success: false, error: '差异已处理，请重新核对。' }
  current.differenceStatus = 'processing'
  current.differenceResolved = false
  current.recheckRequired = false
  current.updatedAt = nowText()
  persist()
  writePayableCheckLog('处理差异', { targetId: current.id, targetNo: current.payableCheckNo })
  return { success: true, payableCheck: clone(current) }
}

export function savePayableCheckDifferenceHandling(id, payload = {}) {
  const current = byId(state.payableChecks, id)
  if (!current) return { success: false, error: '未找到应付核对单。' }
  normalizeCurrentStatus(current)
  if (current.checkStatus !== 'difference') return { success: false, error: '当前应付核对不是差异状态。' }
  if (!payload.differenceType) return { success: false, error: '请选择差异类型。' }
  if (!String(payload.differenceReason || '').trim()) return { success: false, error: '请填写差异原因。' }
  if (!payload.differenceResolution) return { success: false, error: '请选择处理方式。' }
  const stamp = nowText()
  current.differenceStatus = 'resolved'
  current.differenceType = payload.differenceType
  current.differenceReason = String(payload.differenceReason || '').trim()
  current.differenceResolution = payload.differenceResolution
  current.remark = payload.remark || current.remark || ''
  current.differenceHandlerId = payload.differenceHandlerId || current.differenceHandlerId || 'current-user'
  current.differenceHandlerName = payload.differenceHandlerName || current.differenceHandlerName || '当前处理人'
  current.differenceHandledAt = stamp
  current.differenceResolved = true
  current.recheckRequired = true
  current.recheckResult = ''
  current.updatedAt = stamp
  current.lines = (current.lines || []).map((line) => ({
    ...line,
    differenceType: line.differenceType || current.differenceType,
    differenceReason: line.differenceReason || current.differenceReason,
    differenceResolution: line.differenceResolution || current.differenceResolution,
    differenceResolved: true,
  }))
  persist()
  writePayableCheckLog('保存差异处理', { targetId: current.id, targetNo: current.payableCheckNo, result: current.differenceReason })
  return { success: true, payableCheck: clone(current) }
}

export function cancelPayableCheckDifferenceHandling(id) {
  const current = byId(state.payableChecks, id)
  if (!current) return { success: false, error: '未找到应付核对单。' }
  normalizeCurrentStatus(current)
  if (current.checkStatus !== 'difference' || current.differenceStatus !== 'processing') return { success: false, error: '当前没有正在处理的差异。' }
  current.differenceStatus = 'pending'
  current.differenceResolved = false
  current.recheckRequired = false
  current.updatedAt = nowText()
  persist()
  writePayableCheckLog('取消差异处理', { targetId: current.id, targetNo: current.payableCheckNo })
  return { success: true, payableCheck: clone(current) }
}

export function recheckPayableCheckAfterDifference(id) {
  const current = byId(state.payableChecks, id)
  if (!current) return { success: false, error: '未找到应付核对单。' }
  normalizeCurrentStatus(current)
  if (current.checkStatus !== 'difference' || current.differenceStatus !== 'resolved' || current.differenceResolved !== true) {
    return { success: false, error: '差异尚未处理，不能重新核对。' }
  }
  current.checkStatus = 'checking'
  current.recheckRequired = false
  current.recheckedAt = nowText()
  current.recheckResult = 'rechecking'
  current.invoicePrepareReady = false
  current.updatedAt = current.recheckedAt
  persist()
  writePayableCheckLog('重新核对', { targetId: current.id, targetNo: current.payableCheckNo })
  return { success: true, payableCheck: clone(current) }
}

export function markPayableCheckInvoicePrepared(id, invoicePrepare = {}) {
  const current = byId(state.payableChecks, id)
  if (!current) return { success: false, error: '未找到应付核对单。' }
  const stamp = nowText()
  current.checkStatus = 'invoicePrepared'
  current.invoicePrepareReady = true
  current.invoicePrepareGenerated = true
  current.targetInvoicePrepareId = invoicePrepare.id || invoicePrepare.invoicePrepareId || current.targetInvoicePrepareId || ''
  current.targetInvoicePrepareNo = invoicePrepare.invoicePrepareNo || current.targetInvoicePrepareNo || ''
  current.targetModule = 'invoicePrepare'
  current.invoicePreparedAt = stamp
  current.updatedAt = stamp
  persist()
  writePayableCheckLog('生成发票预备成功后回写应付核对状态', { targetId: current.id, targetNo: current.payableCheckNo, result: current.targetInvoicePrepareNo || '已生成发票预备' })
  return { success: true, payableCheck: clone(current) }
}

export function cancelPayableCheck(id) {
  return markStatus(id, 'cancelled', '取消应付核对')
}

export function batchMarkPayableCheckChecking(ids = []) {
  return batchResult(ids, markPayableCheckChecking, '批量标记核对中', (id) => byId(state.payableChecks, id)?.payableCheckNo || id)
}

export function batchMarkPayableCheckChecked(ids = []) {
  return batchResult(ids, markPayableCheckChecked, '批量标记已核对', (id) => byId(state.payableChecks, id)?.payableCheckNo || id)
}

export function batchMarkPayableCheckDifference(ids = []) {
  return batchResult(ids, markPayableCheckDifference, '批量标记存在差异', (id) => byId(state.payableChecks, id)?.payableCheckNo || id)
}

export function batchMarkInvoicePrepareReady(ids = []) {
  return batchResult(ids, markInvoicePrepareReady, '批量标记可生成发票预备', (id) => byId(state.payableChecks, id)?.payableCheckNo || id)
}
