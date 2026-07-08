import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import { getWmsState, getInventoryTransactionById } from '../wms/wmsStore.js'
import { getIncomingInspectionById, getQmsState } from '../qms/qmsStore.js'
import { getPurchaseReceiveById, listPurchaseReceives } from '../wms/purchaseReceiveStore.js'
import { getScmPurchaseOrderItems, getScmState } from '../scm/scmStore.js'

const STORAGE_KEY = 'payable-prepare-state-v1'
const ALLOWED_TRANSACTION_TYPES = ['purchaseInspectionIn', 'concessionIn']
const BLOCKED_TRANSACTION_TYPES = ['return', 'scrap', 'rework', 'adjustment', 'transfer', 'lock', 'unlock', 'purchaseReceivePrepare', 'incomingInspection']

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
  return { payablePrepares: [] }
}

function byId(collection, id) {
  return (collection || []).find((item) => String(item.id) === String(id)) || null
}

function byNo(collection, fields, no) {
  if (!no) return null
  return (collection || []).find((item) => fields.some((field) => String(item?.[field] || '') === String(no))) || null
}

function findPurchaseOrder(transaction = {}) {
  return (getScmState().purchaseOrders || []).find((item) => (
    String(item.id || '') === String(transaction.sourcePurchaseOrderId || '')
    || String(item.poNo || '') === String(transaction.sourcePurchaseOrderNo || '')
  )) || null
}

function findPurchaseReceive(transaction = {}) {
  if (transaction.sourceReceiveId) {
    const receive = getPurchaseReceiveById(transaction.sourceReceiveId)
    if (receive?.id) return receive
  }
  return byNo(listPurchaseReceives(), ['receiveNo', 'sourceReceiveNo', 'sourceOrderNo'], transaction.sourceReceiveNo)
}

function findIncomingInspection(transaction = {}) {
  if (transaction.sourceInspectionId) {
    const inspection = getIncomingInspectionById(transaction.sourceInspectionId)
    if (inspection?.id) return inspection
  }
  return byNo(getQmsState().incomingInspections || [], ['inspectionNo', 'sourceInspectionNo'], transaction.sourceInspectionNo)
}

function normalizeInventoryTransaction(transaction = {}) {
  const transactionType = transaction.transactionType || transaction.type || transaction.businessType || ''
  const quantity = toNumber(transaction.quantity ?? transaction.qty ?? transaction.changeQty)
  const normalized = {
    ...transaction,
    id: transaction.id || transaction.transactionId || transaction.transactionNo || '',
    transactionNo: transaction.transactionNo || transaction.transactionId || transaction.id || '',
    transactionType,
    quantity,
    afterQty: toNumber(transaction.afterQty ?? transaction.afterQuantity),
    sourcePurchaseOrderNo: transaction.sourcePurchaseOrderNo || transaction.poNo || transaction.purchaseOrderNo || '',
    sourceInspectionNo: transaction.sourceInspectionNo || transaction.inspectionNo || '',
    sourceReceiveNo: transaction.sourceReceiveNo || transaction.receiveNo || '',
    supplierName: transaction.supplierName || transaction.supplier || '',
    buyerName: transaction.buyerName || transaction.buyer || '',
    sourceModule: transaction.sourceModule || '',
  }
  if (!normalized.sourceModule && ALLOWED_TRANSACTION_TYPES.includes(transactionType)) normalized.sourceModule = 'qms'

  const order = findPurchaseOrder(normalized) || {}
  const receive = findPurchaseReceive(normalized) || {}
  const inspection = findIncomingInspection(normalized) || {}
  return {
    ...normalized,
    sourceInspectionId: normalized.sourceInspectionId || inspection.id || '',
    sourceInspectionNo: normalized.sourceInspectionNo || inspection.inspectionNo || '',
    sourceReceiveId: normalized.sourceReceiveId || receive.id || inspection.sourceReceiveId || '',
    sourceReceiveNo: normalized.sourceReceiveNo || receive.receiveNo || inspection.sourceReceiveNo || '',
    sourcePurchaseOrderId: normalized.sourcePurchaseOrderId || order.id || inspection.sourcePurchaseOrderId || inspection.sourceOrderId || receive.sourceOrderId || '',
    sourcePurchaseOrderNo: normalized.sourcePurchaseOrderNo || order.poNo || inspection.sourcePurchaseOrderNo || inspection.sourceOrderNo || receive.sourcePurchaseOrderNo || receive.sourceOrderNo || '',
    rootRequestNo: normalized.rootRequestNo || inspection.rootRequestNo || receive.rootRequestNo || order.rootRequestNo || '',
    supplierId: normalized.supplierId || inspection.supplierId || receive.supplierId || order.supplierId || '',
    supplierName: normalized.supplierName || inspection.supplierName || receive.supplierName || order.supplierName || '',
    buyerId: normalized.buyerId || inspection.buyerId || receive.buyerId || order.buyerId || '',
    buyerName: normalized.buyerName || inspection.buyerName || receive.buyerName || order.buyerName || '',
    warehouseName: normalized.warehouseName || receive.warehouseName || inspection.warehouseName || '',
    locationName: normalized.locationName || '',
  }
}

function normalizeLine(line = {}, index = 0) {
  const payableQty = toNumber(line.payableQty)
  const payablePrice = toNumber(line.payablePrice)
  return {
    id: line.id || createId('ppl'),
    lineNo: line.lineNo || index + 1,
    materialId: line.materialId || '',
    materialCode: line.materialCode || '',
    materialName: line.materialName || '',
    spec: line.spec || line.specification || '',
    unit: line.unit || '',
    batchNo: line.batchNo || '',
    warehouseId: line.warehouseId || '',
    warehouseName: line.warehouseName || '',
    locationId: line.locationId || '',
    locationName: line.locationName || '',
    qualityStatus: line.qualityStatus || '',
    receivedQty: toNumber(line.receivedQty),
    qualifiedQty: toNumber(line.qualifiedQty),
    concessionQty: toNumber(line.concessionQty),
    payableQty,
    planPrice: toNumber(line.planPrice),
    planAmount: roundAmount(line.planAmount),
    actualPrice: toNumber(line.actualPrice),
    actualAmount: roundAmount(line.actualAmount),
    payablePrice,
    payableAmount: roundAmount(line.payableAmount || payableQty * payablePrice),
    sourceInspectionLineId: line.sourceInspectionLineId || '',
    sourceReceiveLineId: line.sourceReceiveLineId || '',
    sourcePurchaseOrderLineId: line.sourcePurchaseOrderLineId || '',
    sourceInventoryTransactionId: line.sourceInventoryTransactionId || '',
    sourceInventoryTransactionNo: line.sourceInventoryTransactionNo || '',
    sourcePurchaseOrderNo: line.sourcePurchaseOrderNo || '',
    rootRequestNo: line.rootRequestNo || '',
    remark: line.remark || '',
  }
}

function summarizeLines(lines = []) {
  return {
    totalReceivedQty: lines.reduce((sum, line) => sum + toNumber(line.receivedQty), 0),
    totalQualifiedQty: lines.reduce((sum, line) => sum + toNumber(line.qualifiedQty), 0),
    totalConcessionQty: lines.reduce((sum, line) => sum + toNumber(line.concessionQty), 0),
    totalPayableQty: lines.reduce((sum, line) => sum + toNumber(line.payableQty), 0),
    totalPlanAmount: roundAmount(lines.reduce((sum, line) => sum + toNumber(line.planAmount), 0)),
    totalActualAmount: roundAmount(lines.reduce((sum, line) => sum + toNumber(line.actualAmount), 0)),
    totalPayableAmount: roundAmount(lines.reduce((sum, line) => sum + toNumber(line.payableAmount), 0)),
  }
}

function payablePrepare(payload = {}) {
  const stamp = nowText()
  const lines = (payload.lines || []).map(normalizeLine)
  const summary = summarizeLines(lines)
  const totalPayableAmount = roundAmount(payload.totalPayableAmount ?? summary.totalPayableAmount)
  const totalPlanAmount = roundAmount(payload.totalPlanAmount ?? summary.totalPlanAmount)
  return {
    id: payload.id || createId('pp'),
    payablePrepareNo: payload.payablePrepareNo || createNo('PP'),
    sourceModule: payload.sourceModule || 'wms.inventoryTransaction',
    sourceInventoryTransactionIds: payload.sourceInventoryTransactionIds || [],
    sourceInspectionId: payload.sourceInspectionId || '',
    sourceInspectionNo: payload.sourceInspectionNo || '',
    sourceReceiveId: payload.sourceReceiveId || '',
    sourceReceiveNo: payload.sourceReceiveNo || '',
    sourcePurchaseOrderId: payload.sourcePurchaseOrderId || '',
    sourcePurchaseOrderNo: payload.sourcePurchaseOrderNo || '',
    rootRequestNo: payload.rootRequestNo || '',
    supplierId: payload.supplierId || '',
    supplierName: payload.supplierName || '',
    buyerId: payload.buyerId || '',
    buyerName: payload.buyerName || '',
    requestDepartment: payload.requestDepartment || '',
    demandDepartment: payload.demandDepartment || '',
    purchaseDepartment: payload.purchaseDepartment || '',
    payableType: payload.payableType || 'purchaseInbound',
    payableStatus: payload.payableStatus || 'prepared',
    inventoryPostedAt: payload.inventoryPostedAt || '',
    prepareDate: payload.prepareDate || today(),
    expectedInvoiceDate: payload.expectedInvoiceDate || '',
    expectedPayDate: payload.expectedPayDate || '',
    totalReceivedQty: toNumber(payload.totalReceivedQty ?? summary.totalReceivedQty),
    totalQualifiedQty: toNumber(payload.totalQualifiedQty ?? summary.totalQualifiedQty),
    totalConcessionQty: toNumber(payload.totalConcessionQty ?? summary.totalConcessionQty),
    totalPayableQty: toNumber(payload.totalPayableQty ?? summary.totalPayableQty),
    totalPlanAmount,
    totalActualAmount: roundAmount(payload.totalActualAmount ?? summary.totalActualAmount),
    totalPayableAmount,
    amountVariance: roundAmount(payload.amountVariance ?? totalPayableAmount - totalPlanAmount),
    settlementBasis: payload.settlementBasis || 'inspectionQualified',
    settlementReady: payload.settlementReady ?? true,
    invoiceReady: payload.invoiceReady ?? false,
    paymentReady: payload.paymentReady ?? false,
    duplicateCheckKey: payload.duplicateCheckKey || '',
    remark: payload.remark || '',
    lines,
    createdAt: payload.createdAt || stamp,
    updatedAt: payload.updatedAt || stamp,
  }
}

function normalizeState(raw = {}) {
  return { payablePrepares: (raw.payablePrepares || []).map(payablePrepare) }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[PAYABLE PREPARE STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export function writePayablePrepareLog(action, payload = {}) {
  addOperationLog({
    module: '采购应付预备',
    action,
    targetType: payload.targetType || 'payablePrepare',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源模块：${payload.sourceModule || 'WMS库存流水'}`,
      `来源单据：${payload.sourceNo || '-'}`,
      `结果：${payload.result || '成功'}`,
    ].join('；'),
  })
}

export function getPayablePrepareState() {
  return clone(state)
}

export function savePayablePrepareState(nextState) {
  state = normalizeState(nextState)
  persist()
  writePayablePrepareLog('保存应付预备状态', { targetType: 'payablePrepareState', targetId: 'state' })
  return getPayablePrepareState()
}

export function resetPayablePrepareState() {
  state = defaultState()
  persist()
  writePayablePrepareLog('恢复应付预备演示数据', { targetType: 'payablePrepareState', targetId: 'demo' })
  return getPayablePrepareState()
}

export function listPayablePrepares() {
  return clone(state.payablePrepares)
}

export function getPayablePrepareById(id) {
  return clone(byId(state.payablePrepares, id))
}

function duplicateKeyFromTransaction(transaction = {}) {
  const source = normalizeInventoryTransaction(transaction)
  return [
    source.sourceInspectionNo,
    source.sourceReceiveNo,
    source.sourcePurchaseOrderNo,
    source.materialId,
    source.batchNo,
    source.qualityStatus,
  ].map((item) => String(item || '')).join('|')
}

export function isPayablePrepareGenerated(transactionOrId) {
  const transaction = normalizeInventoryTransaction(typeof transactionOrId === 'object' ? transactionOrId : getInventoryTransactionById(transactionOrId))
  if (!transaction?.id) return false
  const duplicateKey = duplicateKeyFromTransaction(transaction)
  return state.payablePrepares.some((prepare) => (
    (prepare.sourceInventoryTransactionIds || []).includes(transaction.id)
    || prepare.duplicateCheckKey === duplicateKey
    || (prepare.lines || []).some((line) => line.sourceInventoryTransactionId === transaction.id)
  ))
}

function sourcePurchaseOrderLine(transaction = {}) {
  const source = normalizeInventoryTransaction(transaction)
  const order = findPurchaseOrder(source)
  const lines = order?.id ? getScmPurchaseOrderItems(order.id) : []
  return lines.find((line) => (
    String(line.materialId || '') === String(source.materialId || '')
    || String(line.materialCode || '') === String(source.materialCode || '')
  )) || {}
}

function sourceReceiveLine(transaction = {}) {
  const source = normalizeInventoryTransaction(transaction)
  const receive = findPurchaseReceive(source)
  return (receive?.lines || []).find((line) => (
    String(line.materialId || '') === String(source.materialId || '')
    || String(line.materialCode || '') === String(source.materialCode || '')
  )) || {}
}

function sourceInspectionLine(transaction = {}) {
  const source = normalizeInventoryTransaction(transaction)
  const inspection = findIncomingInspection(source)
  return (inspection?.lines || []).find((line) => (
    String(line.materialId || '') === String(source.materialId || '')
    || String(line.materialCode || '') === String(source.materialCode || '')
  )) || {}
}

function canUseTransaction(transaction = {}) {
  const source = normalizeInventoryTransaction(transaction)
  if (BLOCKED_TRANSACTION_TYPES.includes(source.transactionType)) return { success: false, error: '退货、报废、返工、调整、调拨、锁定、未检验或未入库数据不能进入应付预备。' }
  if (!ALLOWED_TRANSACTION_TYPES.includes(source.transactionType)) return { success: false, error: '仅采购检验合格入库和让步接收入库可生成应付预备。' }
  if (source.sourceModule && source.sourceModule !== 'qms') return { success: false, error: '仅 QMS 确认入库流水可进入应付预备。' }
  if (toNumber(source.quantity) <= 0) return { success: false, error: '入库数量必须大于 0。' }
  if (!source.supplierId && !source.supplierName) return { success: false, error: '来源流水缺少供应商信息。' }
  if (!source.sourcePurchaseOrderNo) return { success: false, error: '来源流水缺少采购订单号。' }
  if (isPayablePrepareGenerated(source)) return { success: false, error: '该入库流水已生成应付预备，不能重复生成。' }
  return { success: true }
}

export function getPayablePrepareSourcesFromInventory() {
  return (getWmsState().inventoryTransactions || [])
    .map(normalizeInventoryTransaction)
    .filter((transaction) => ALLOWED_TRANSACTION_TYPES.includes(transaction.transactionType))
    .filter((transaction) => !transaction.sourceModule || transaction.sourceModule === 'qms')
    .filter((transaction) => toNumber(transaction.quantity) > 0)
    .filter((transaction) => transaction.supplierId || transaction.supplierName)
    .filter((transaction) => transaction.sourcePurchaseOrderNo)
    .map((transaction) => ({
      ...transaction,
      payablePrepareGenerated: isPayablePrepareGenerated(transaction),
      duplicateCheckKey: duplicateKeyFromTransaction(transaction),
      sourceWarning: !transaction.supplierId && transaction.supplierName ? '供应商 ID 缺失，后续需补齐。' : '',
    }))
}

export function getPayablePrepareSourceRejectReason(transaction = {}) {
  const guard = canUseTransaction(transaction)
  return guard.success ? '' : guard.error
}

export function diagnosePayablePrepareSources() {
  const transactions = (getWmsState().inventoryTransactions || []).map(normalizeInventoryTransaction)
  const rejectReasons = {}
  const summary = {
    totalInventoryTransactions: transactions.length,
    qmsInventoryTransactions: 0,
    purchaseInspectionInCount: 0,
    concessionInCount: 0,
    alreadyPreparedCount: 0,
    missingSupplierCount: 0,
    missingPurchaseOrderCount: 0,
    missingQuantityCount: 0,
    eligibleCount: 0,
    rejectedCount: 0,
    rejectReasons,
  }
  transactions.forEach((transaction) => {
    if (transaction.sourceModule === 'qms') summary.qmsInventoryTransactions += 1
    if (transaction.transactionType === 'purchaseInspectionIn') summary.purchaseInspectionInCount += 1
    if (transaction.transactionType === 'concessionIn') summary.concessionInCount += 1
    if (!transaction.supplierId && !transaction.supplierName) summary.missingSupplierCount += 1
    if (!transaction.sourcePurchaseOrderNo) summary.missingPurchaseOrderCount += 1
    if (toNumber(transaction.quantity) <= 0) summary.missingQuantityCount += 1
    const guard = canUseTransaction(transaction)
    if (guard.success) {
      summary.eligibleCount += 1
      return
    }
    if (isPayablePrepareGenerated(transaction)) summary.alreadyPreparedCount += 1
    summary.rejectedCount += 1
    rejectReasons[guard.error] = (rejectReasons[guard.error] || 0) + 1
  })
  return summary
}

export function diagnosePayablePrepareSourcesByPurchaseOrder(poNo) {
  const targetNo = String(poNo || '').trim()
  if (!targetNo) return []
  return (getWmsState().inventoryTransactions || [])
    .map(normalizeInventoryTransaction)
    .filter((transaction) => String(transaction.sourcePurchaseOrderNo || '') === targetNo)
    .map((transaction) => {
      const guard = canUseTransaction(transaction)
      return {
        id: transaction.id,
        transactionNo: transaction.transactionNo,
        transactionType: transaction.transactionType,
        qualityStatus: transaction.qualityStatus,
        quantity: transaction.quantity,
        sourcePurchaseOrderNo: transaction.sourcePurchaseOrderNo,
        materialCode: transaction.materialCode,
        materialName: transaction.materialName,
        canCreatePayablePrepare: guard.success,
        rejectReason: guard.success ? '' : guard.error,
      }
    })
}

export function getPayablePrepareSourceSummary() {
  const summary = diagnosePayablePrepareSources()
  const reasons = []
  if (!summary.totalInventoryTransactions) reasons.push('当前没有库存流水。')
  else if (!summary.qmsInventoryTransactions) reasons.push('当前没有 QMS 确认入库流水。')
  else if (!summary.purchaseInspectionInCount && !summary.concessionInCount) reasons.push('有库存流水，但不是采购检验合格入库或让步接收入库。')
  if (summary.missingSupplierCount) reasons.push('部分合格/让步入库流水缺少供应商信息。')
  if (summary.missingPurchaseOrderCount) reasons.push('部分合格/让步入库流水缺少来源采购订单号。')
  if (summary.missingQuantityCount) reasons.push('部分入库流水数量无效。')
  if (summary.alreadyPreparedCount && !summary.eligibleCount) reasons.push('所有符合条件的入库流水都已生成应付预备。')
  Object.entries(summary.rejectReasons).forEach(([reason, count]) => reasons.push(`${reason}（${count} 条）`))
  return { ...summary, reasons: Array.from(new Set(reasons)) }
}

function buildPayableLine(transaction = {}) {
  const source = normalizeInventoryTransaction(transaction)
  const receiveLine = sourceReceiveLine(source)
  const orderLine = sourcePurchaseOrderLine(source)
  const inspectionLine = sourceInspectionLine(source)
  const payableQty = toNumber(source.quantity)
  const planPrice = toNumber(source.planPrice || receiveLine.planPrice || orderLine.planPrice || orderLine.price)
  const actualPrice = toNumber(source.actualPrice || receiveLine.actualPrice)
  const payablePrice = toNumber(actualPrice || source.payablePrice || receiveLine.payablePrice || planPrice || orderLine.planPrice || 0)
  const planAmount = roundAmount(payableQty * planPrice)
  const actualAmount = roundAmount(payableQty * (actualPrice || payablePrice))
  return normalizeLine({
    materialId: source.materialId,
    materialCode: source.materialCode,
    materialName: source.materialName,
    spec: source.spec || source.specification || receiveLine.spec || orderLine.specification || '',
    unit: source.unit || receiveLine.unit || orderLine.unit || '',
    batchNo: source.batchNo,
    warehouseId: source.warehouseId,
    warehouseName: source.warehouseName,
    locationId: source.locationId,
    locationName: source.locationName,
    qualityStatus: source.qualityStatus,
    receivedQty: toNumber(inspectionLine.receivedQty || receiveLine.actualReceiveQty || payableQty),
    qualifiedQty: source.transactionType === 'purchaseInspectionIn' ? payableQty : 0,
    concessionQty: source.transactionType === 'concessionIn' ? payableQty : 0,
    payableQty,
    planPrice,
    planAmount,
    actualPrice,
    actualAmount,
    payablePrice,
    payableAmount: roundAmount(payableQty * payablePrice),
    sourceInspectionLineId: inspectionLine.id || '',
    sourceReceiveLineId: receiveLine.id || '',
    sourcePurchaseOrderLineId: orderLine.id || '',
    sourceInventoryTransactionId: source.id,
    sourceInventoryTransactionNo: source.transactionNo,
    sourcePurchaseOrderNo: source.sourcePurchaseOrderNo,
    rootRequestNo: source.rootRequestNo,
    remark: source.sourceWarning || source.remark || '',
  })
}

export function createPayablePrepareFromInventoryTransaction(transactionId) {
  const transaction = normalizeInventoryTransaction(getInventoryTransactionById(transactionId))
  if (!transaction?.id) return { success: false, error: '未找到库存流水。' }
  const guard = canUseTransaction(transaction)
  if (!guard.success) {
    writePayablePrepareLog('生成应付预备被拦截', {
      sourceNo: transaction.transactionNo || transactionId,
      targetId: transactionId,
      result: guard.error,
    })
    return guard
  }
  const receive = findPurchaseReceive(transaction)
  const order = findPurchaseOrder(transaction) || {}
  const line = buildPayableLine(transaction)
  const summary = summarizeLines([line])
  const prepare = payablePrepare({
    sourceInventoryTransactionIds: [transaction.id],
    sourceInspectionId: transaction.sourceInspectionId,
    sourceInspectionNo: transaction.sourceInspectionNo,
    sourceReceiveId: transaction.sourceReceiveId,
    sourceReceiveNo: transaction.sourceReceiveNo,
    sourcePurchaseOrderId: transaction.sourcePurchaseOrderId,
    sourcePurchaseOrderNo: transaction.sourcePurchaseOrderNo,
    rootRequestNo: transaction.rootRequestNo,
    supplierId: transaction.supplierId,
    supplierName: transaction.supplierName,
    buyerId: transaction.buyerId || order.buyerId || '',
    buyerName: transaction.buyerName || order.buyerName || '',
    requestDepartment: receive?.requestDepartment || order.rootRequestDepartment || order.requestDepartment || '',
    demandDepartment: receive?.demandDepartment || order.rootDemandDepartment || order.demandDepartment || '',
    purchaseDepartment: receive?.purchaseDepartment || order.rootPurchaseDepartment || order.purchaseDepartment || '',
    inventoryPostedAt: transaction.createdAt || transaction.transactionDate,
    duplicateCheckKey: duplicateKeyFromTransaction(transaction),
    totalReceivedQty: summary.totalReceivedQty,
    totalQualifiedQty: summary.totalQualifiedQty,
    totalConcessionQty: summary.totalConcessionQty,
    totalPayableQty: summary.totalPayableQty,
    totalPlanAmount: summary.totalPlanAmount,
    totalActualAmount: summary.totalActualAmount,
    totalPayableAmount: summary.totalPayableAmount,
    amountVariance: roundAmount(summary.totalPayableAmount - summary.totalPlanAmount),
    remark: transaction.sourceWarning || '由采购检验合格/让步接收入库流水生成，仅为应付预备。',
    lines: [line],
  })
  state.payablePrepares.unshift(prepare)
  persist()
  writePayablePrepareLog('从库存流水生成应付预备', {
    sourceNo: transaction.transactionNo,
    targetId: prepare.id,
    targetNo: prepare.payablePrepareNo,
    result: prepare.totalPayableAmount,
  })
  return { success: true, payablePrepareId: prepare.id, payablePrepareNo: prepare.payablePrepareNo, payablePrepare: clone(prepare) }
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
  writePayablePrepareLog(label, { targetType: 'batch', targetId: label, result: `成功 ${result.successCount} 条，失败 ${result.failedCount} 条；${result.failedReason.join('；')}` })
  if (result.failedCount) writePayablePrepareLog('批量操作失败原因', { targetType: 'batch', targetId: label, result: result.failedReason.join('；') })
  return result
}

export function batchCreatePayablePrepareFromInventoryTransactions(ids = []) {
  return batchResult(ids, createPayablePrepareFromInventoryTransaction, '批量生成应付预备', (id) => getInventoryTransactionById(id)?.transactionNo || id)
}

export function updatePayablePrepare(id, patch = {}) {
  const current = byId(state.payablePrepares, id)
  if (!current || ['cancelled', 'closed'].includes(current.payableStatus)) return { success: false, error: '当前应付预备不可修改。' }
  Object.assign(current, payablePrepare({ ...current, ...patch, id: current.id, updatedAt: nowText() }))
  persist()
  writePayablePrepareLog('更新应付预备', { targetId: current.id, targetNo: current.payablePrepareNo })
  return { success: true, payablePrepare: clone(current) }
}

function markStatus(id, status, action) {
  const current = byId(state.payablePrepares, id)
  if (!current) return { success: false, error: '未找到应付预备单。' }
  if (['cancelled', 'closed'].includes(current.payableStatus)) return { success: false, error: '已取消或已关闭的应付预备不能继续流转。' }
  current.payableStatus = status
  current.updatedAt = nowText()
  persist()
  writePayablePrepareLog(action, { targetId: current.id, targetNo: current.payablePrepareNo })
  return { success: true, payablePrepare: clone(current) }
}

export function markPayablePrepareChecking(id) {
  return markStatus(id, 'checking', '标记核对中')
}

export function markPayablePrepareChecked(id) {
  return markStatus(id, 'checked', '标记已核对')
}

export function markPayablePrepareReady(id) {
  return markStatus(id, 'payableReady', '标记可生成应付')
}

export function cancelPayablePrepare(id) {
  return markStatus(id, 'cancelled', '取消应付预备')
}

export function batchMarkPayablePrepareChecking(ids = []) {
  return batchResult(ids, markPayablePrepareChecking, '批量标记核对中', (id) => byId(state.payablePrepares, id)?.payablePrepareNo || id)
}

export function batchMarkPayablePrepareChecked(ids = []) {
  return batchResult(ids, markPayablePrepareChecked, '批量标记已核对', (id) => byId(state.payablePrepares, id)?.payablePrepareNo || id)
}

export function batchMarkPayablePrepareReady(ids = []) {
  return batchResult(ids, markPayablePrepareReady, '批量标记可生成应付', (id) => byId(state.payablePrepares, id)?.payablePrepareNo || id)
}
