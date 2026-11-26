import { getScmState } from './scmStore.js'
import { listPurchaseReceives } from '../wms/purchaseReceiveStore.js'
import { listIncomingInspections } from '../qms/qmsStore.js'
import { getInventoryTransactions } from '../wms/wmsStore.js'
import { listPayablePrepares } from '../finance/payablePrepareStore.js'
import { listPayableChecks } from '../finance/payableCheckStore.js'

const STORAGE_KEY = 'supplier-settlement-state-v1'
const PURCHASE_INBOUND_TYPES = ['purchaseInspectionIn', 'concessionIn', 'purchaseInbound', 'purchaseIn']

const TEXT = {
  supplierPending: '\u5f85\u8865\u5145\u4f9b\u5e94\u5546',
  supplierMissing: '\u4f9b\u5e94\u5546\u6765\u6e90\u7f3a\u5931',
  inventoryPending: '\u5e93\u5b58\u6d41\u6c34\u5f85\u8865\u5145',
  payablePending: '\u5e94\u4ed8\u9884\u5907\u91d1\u989d\u5f85\u8865\u5145',
  inventoryAmountPending: '\u5165\u5e93\u91d1\u989d\u5f85\u8865\u5145',
  amountMatched: '\u91d1\u989d\u4e00\u81f4',
  draftCreated: '\u5df2\u751f\u6210\u7ed3\u7b97\u8349\u7a3f',
  draftExists: '\u5df2\u5b58\u5728\u7ed3\u7b97\u8bb0\u5f55',
  draftLog: '\u751f\u6210\u7ed3\u7b97\u8349\u7a3f',
  draftRemark: '\u4ec5\u751f\u6210\u4f9b\u5e94\u5546\u7ed3\u7b97\u8349\u7a3f\uff0c\u4e0d\u4fee\u6539\u91c7\u8d2d\u3001\u5e93\u5b58\u3001\u5e94\u4ed8\u3001\u4ed8\u6b3e\u3001\u603b\u8d26\u6216\u94f6\u884c\u6d41\u6c34\u3002',
  recalc: '\u91cd\u65b0\u8ba1\u7b97\u5dee\u5f02',
  manualReconciled: '\u4eba\u5de5\u6807\u8bb0\u5df2\u5bf9\u8d26',
  markReconciled: '\u6807\u8bb0\u5df2\u5bf9\u8d26',
  manualDifferencePending: '\u4eba\u5de5\u6807\u8bb0\u5dee\u5f02\u5f85\u5904\u7406',
  markDifferencePending: '\u6807\u8bb0\u5dee\u5f02\u5f85\u5904\u7406',
  closeSettlement: '\u5173\u95ed\u7ed3\u7b97',
  notFound: '\u672a\u627e\u5230\u7ed3\u7b97\u8bb0\u5f55',
  selectDifferenceType: '\u9009\u62e9\u5dee\u5f02\u539f\u56e0',
  confirmDifference: '\u786e\u8ba4\u5dee\u5f02',
  rejectDifference: '\u9a73\u56de\u5dee\u5f02',
  confirmReconciliation: '\u786e\u8ba4\u5bf9\u8d26',
  reconciliationBlocked: '\u5dee\u5f02\u672a\u786e\u8ba4\uff0c\u4e0d\u80fd\u786e\u8ba4\u5bf9\u8d26',
  reconciliationReady: '\u5bf9\u8d26\u5df2\u786e\u8ba4\uff0c\u4ec5\u8868\u793a\u4f9b\u5e94\u5546\u7ed3\u7b97\u53e3\u5f84\u5df2\u786e\u8ba4\uff0c\u4e0d\u4ee3\u8868\u4ed8\u6b3e\u3001\u6838\u9500\u3001\u603b\u8d26\u6216\u94f6\u884c\u6d41\u6c34\u5b8c\u6210\u3002',
}

export const supplierSettlementDifferenceTypes = [
  { value: 'none', label: '\u65e0\u5dee\u5f02' },
  { value: 'price_difference', label: '\u4ef7\u683c\u5dee\u5f02' },
  { value: 'quantity_difference', label: '\u6570\u91cf\u5dee\u5f02' },
  { value: 'tax_difference', label: '\u7a0e\u989d\u5dee\u5f02' },
  { value: 'fee_difference', label: '\u8fd0\u8d39 / \u88c5\u5378\u8d39 / \u5176\u4ed6\u8d39\u7528\u5dee\u5f02' },
  { value: 'inspection_difference', label: '\u68c0\u9a8c\u5dee\u5f02' },
  { value: 'return_or_deduction', label: '\u9000\u8d27\u3001\u6263\u6b3e\u6216\u6298\u8ba9\u5dee\u5f02' },
  { value: 'source_missing', label: '\u6765\u6e90\u5355\u636e\u7f3a\u5931' },
  { value: 'payable_prepare_missing', label: '\u5e94\u4ed8\u9884\u5907\u7f3a\u5931' },
  { value: 'manual_pending', label: '\u4eba\u5de5\u5f85\u786e\u8ba4' },
  { value: 'unknown', label: '\u672a\u77e5\u5dee\u5f02' },
]

export const supplierSettlementDifferenceConfirmStatuses = [
  { value: 'not_required', label: '\u4e0d\u9700\u8981\u786e\u8ba4' },
  { value: 'pending', label: '\u5f85\u786e\u8ba4' },
  { value: 'confirmed', label: '\u5df2\u786e\u8ba4' },
  { value: 'rejected', label: '\u5df2\u9a73\u56de' },
  { value: 'closed', label: '\u5df2\u5173\u95ed' },
]

export const supplierSettlementReconciliationConfirmStatuses = [
  { value: 'not_ready', label: '\u672a\u51c6\u5907\u597d' },
  { value: 'ready', label: '\u53ef\u786e\u8ba4' },
  { value: 'confirmed', label: '\u5df2\u786e\u8ba4' },
  { value: 'blocked', label: '\u963b\u65ad' },
]

function clone(value) {
  return JSON.parse(JSON.stringify(value ?? null))
}

function nowText() {
  return new Date().toISOString()
}

function clean(value) {
  return value == null ? '' : String(value).trim()
}

function toArray(value) {
  if (Array.isArray(value)) return value.filter(Boolean)
  return value ? [value] : []
}

function amount(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : 0
}

function roundAmount(value) {
  return Math.round(amount(value) * 100) / 100
}

function firstNo(record = {}, fields = []) {
  for (const field of fields) {
    const value = clean(record[field])
    if (value) return value
  }
  return ''
}

function sourcePoNo(record = {}) {
  return firstNo(record, ['sourcePurchaseOrderNo', 'purchaseOrderNo', 'poNo', 'sourcePoNo', 'orderNo', 'sourceOrderNo'])
}

function receiveNo(record = {}) {
  return firstNo(record, ['receiveNo', 'receiptNo', 'sourceReceiveNo', 'purchaseReceiveNo'])
}

function inspectionNo(record = {}) {
  return firstNo(record, ['inspectionNo', 'iqcNo', 'sourceInspectionNo'])
}

function inventoryTransactionNo(record = {}) {
  return firstNo(record, ['transactionNo', 'txnNo', 'inventoryTransactionNo'])
}

function payablePrepareNo(record = {}) {
  return firstNo(record, ['payablePrepareNo', 'prepareNo', 'sourcePayablePrepareNo'])
}

function amountDifference(values = []) {
  const available = values.map(amount).filter((item) => item > 0)
  if (available.length <= 1) return 0
  return roundAmount(Math.max(...available) - Math.min(...available))
}

function basisSettlementAmount(values = []) {
  const available = values.map(amount).filter((item) => item > 0)
  return available.length ? roundAmount(Math.min(...available)) : 0
}

function buildSourceKey(row = {}) {
  const payableCheckKey = clean(row.sourcePayableCheckId || row.payableCheckId || row.sourcePayableCheckNo || row.payableCheckNo)
  if (payableCheckKey) return `payable-check::${payableCheckKey}`
  return [
    row.supplierId || row.supplierName || 'unknown-supplier',
    row.purchaseOrderNo || 'unknown-po',
    toArray(row.inventoryTransactionNos).join('|') || row.inspectionNo || row.receiveNo || 'source-pending',
  ].join('::')
}

function resolveReconciliationStatus(row = {}) {
  if (!row.purchaseOrderNo || !row.supplierName) return 'source_missing'
  if (!toArray(row.inventoryTransactionNos).length) return 'source_missing'
  if (roundAmount(row.inventoryAmount) <= 0 || roundAmount(row.payablePrepareAmount) <= 0) return 'source_missing'
  if (roundAmount(row.differenceAmount) === 0) return 'matched'
  return 'amount_difference'
}

function typeText(type) {
  return supplierSettlementDifferenceTypes.find((item) => item.value === type)?.label || type || ''
}

function statusText(options, status) {
  return options.find((item) => item.value === status)?.label || status || ''
}

function isSourceMissing(row = {}) {
  return !row.purchaseOrderNo || !row.supplierName || !toArray(row.inventoryTransactionNos).length || roundAmount(row.inventoryAmount) <= 0
}

function isPayablePrepareMissing(row = {}) {
  return roundAmount(row.payablePrepareAmount) <= 0 || !toArray(row.payablePrepareNos).length
}

function resolveDifferenceType(row = {}) {
  if (row.differenceType) return row.differenceType
  if (roundAmount(row.differenceAmount) === 0 && !isSourceMissing(row) && !isPayablePrepareMissing(row)) return 'none'
  if (isPayablePrepareMissing(row)) return 'payable_prepare_missing'
  if (isSourceMissing(row)) return 'source_missing'
  if (row.reconciliationStatus === 'quantity_difference') return 'quantity_difference'
  if (roundAmount(row.differenceAmount) !== 0) return 'manual_pending'
  return 'unknown'
}

function resolveDifferenceConfirmStatus(row = {}) {
  if (row.differenceConfirmStatus) return row.differenceConfirmStatus
  const differenceType = resolveDifferenceType(row)
  if (differenceType === 'none' && roundAmount(row.differenceAmount) === 0) return 'not_required'
  return 'pending'
}

function resolveReconciliationConfirmStatus(row = {}) {
  if (row.reconciliationConfirmStatus === 'confirmed') return 'confirmed'
  const differenceConfirmStatus = resolveDifferenceConfirmStatus(row)
  if (differenceConfirmStatus === 'not_required' || differenceConfirmStatus === 'confirmed') return 'ready'
  if (differenceConfirmStatus === 'pending' || differenceConfirmStatus === 'rejected') return 'blocked'
  return 'not_ready'
}

function resolveNextStepReadiness(row = {}) {
  return row.reconciliationConfirmStatus === 'confirmed' ? 'ready_for_invoice_prepare' : 'not_ready'
}

function logEntry(action, beforeStatus, afterStatus, remark, row = {}, operator = 'system') {
  return {
    action,
    beforeStatus,
    afterStatus,
    operator,
    time: nowText(),
    remark: remark || action,
    differenceType: row.differenceType || '',
    reconciliationConfirmStatus: row.reconciliationConfirmStatus || '',
  }
}

function buildDifferenceReason(row = {}) {
  const reasons = []
  if (!row.supplierName) reasons.push(TEXT.supplierMissing)
  if (!toArray(row.inventoryTransactionNos).length) reasons.push(TEXT.inventoryPending)
  if (roundAmount(row.inventoryAmount) <= 0) reasons.push(TEXT.inventoryAmountPending)
  if (roundAmount(row.payablePrepareAmount) <= 0) reasons.push(TEXT.payablePending)
  if (roundAmount(row.differenceAmount) !== 0) {
    reasons.push(`\u91c7\u8d2d\u3001\u5165\u5e93\u3001\u5e94\u4ed8\u9884\u5907\u91d1\u989d\u5dee\u5f02 ${roundAmount(row.differenceAmount).toFixed(2)}`)
  }
  return reasons.length ? reasons.join('\uff1b') : TEXT.amountMatched
}

function settlementRecord(payload = {}) {
  const purchaseAmount = roundAmount(payload.purchaseAmount)
  const inventoryAmount = roundAmount(payload.inventoryAmount)
  const payablePrepareAmount = roundAmount(payload.payablePrepareAmount)
  const differenceAmount = roundAmount(payload.differenceAmount ?? amountDifference([purchaseAmount, inventoryAmount, payablePrepareAmount]))
  const reconciliationStatus = payload.reconciliationStatus || resolveReconciliationStatus({ ...payload, differenceAmount })
  const settlementStatus = payload.settlementStatus || (reconciliationStatus === 'matched' ? 'reconciling' : 'difference_pending')
  const baseForStatus = { ...payload, purchaseAmount, inventoryAmount, payablePrepareAmount, differenceAmount, reconciliationStatus }
  const differenceType = resolveDifferenceType(baseForStatus)
  const differenceConfirmStatus = resolveDifferenceConfirmStatus({ ...baseForStatus, differenceType })
  const reconciliationConfirmStatus = payload.reconciliationConfirmStatus || resolveReconciliationConfirmStatus({ ...baseForStatus, differenceType, differenceConfirmStatus })
  const nextStepReadiness = payload.nextStepReadiness || resolveNextStepReadiness({ reconciliationConfirmStatus })
  return {
    id: payload.id || `supplier-settlement-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    settlementNo: payload.settlementNo || `SET${new Date().toISOString().replace(/\D/g, '').slice(0, 14)}${Math.floor(Math.random() * 90 + 10)}`,
    supplierId: clean(payload.supplierId),
    supplierName: clean(payload.supplierName) || clean(payload.supplierId) || TEXT.supplierPending,
    purchaseOrderNo: clean(payload.purchaseOrderNo),
    receiveNo: clean(payload.receiveNo),
    inspectionNo: clean(payload.inspectionNo),
    inventoryTransactionNos: toArray(payload.inventoryTransactionNos),
    payablePrepareNos: toArray(payload.payablePrepareNos),
    sourcePayableCheckId: clean(payload.sourcePayableCheckId),
    sourcePayableCheckNo: clean(payload.sourcePayableCheckNo),
    sourcePayablePrepareId: clean(payload.sourcePayablePrepareId),
    sourcePayablePrepareNo: clean(payload.sourcePayablePrepareNo),
    sourceInventoryTransactionIds: toArray(payload.sourceInventoryTransactionIds),
    sourceInventoryTransactionNos: toArray(payload.sourceInventoryTransactionNos || payload.inventoryTransactionNos),
    sourceWarehouseTaskId: clean(payload.sourceWarehouseTaskId),
    sourceWarehouseTaskNo: clean(payload.sourceWarehouseTaskNo),
    sourceInspectionId: clean(payload.sourceInspectionId),
    sourceInspectionNo: clean(payload.sourceInspectionNo || payload.inspectionNo),
    sourceReceiveId: clean(payload.sourceReceiveId),
    sourceReceiveNo: clean(payload.sourceReceiveNo || payload.receiveNo),
    sourcePurchaseOrderId: clean(payload.sourcePurchaseOrderId),
    sourcePurchaseOrderNo: clean(payload.sourcePurchaseOrderNo || payload.purchaseOrderNo),
    sourcePriceApprovalNo: clean(payload.sourcePriceApprovalNo),
    materialId: clean(payload.materialId),
    materialCode: clean(payload.materialCode),
    materialName: clean(payload.materialName),
    unit: clean(payload.unit),
    settlementQuantity: amount(payload.settlementQuantity),
    unitPrice: roundAmount(payload.unitPrice),
    payableAmount: roundAmount(payload.payableAmount),
    checkedAmount: roundAmount(payload.checkedAmount),
    currency: clean(payload.currency),
    lines: Array.isArray(payload.lines) ? clone(payload.lines) : [],
    purchaseAmount,
    inventoryAmount,
    payablePrepareAmount,
    settlementAmount: roundAmount(payload.settlementAmount ?? basisSettlementAmount([purchaseAmount, inventoryAmount, payablePrepareAmount])),
    differenceAmount,
    reconciliationStatus,
    settlementStatus,
    differenceReason: payload.differenceReason || buildDifferenceReason({ ...payload, differenceAmount }),
    differenceType,
    differenceTypeText: payload.differenceTypeText || typeText(differenceType),
    differenceConfirmStatus,
    differenceConfirmStatusText: payload.differenceConfirmStatusText || statusText(supplierSettlementDifferenceConfirmStatuses, differenceConfirmStatus),
    differenceConfirmRemark: payload.differenceConfirmRemark || '',
    differenceConfirmedBy: payload.differenceConfirmedBy || '',
    differenceConfirmedAt: payload.differenceConfirmedAt || '',
    reconciliationConfirmStatus,
    reconciliationConfirmStatusText: payload.reconciliationConfirmStatusText || statusText(supplierSettlementReconciliationConfirmStatuses, reconciliationConfirmStatus),
    reconciliationConfirmedBy: payload.reconciliationConfirmedBy || '',
    reconciliationConfirmedAt: payload.reconciliationConfirmedAt || '',
    reconciliationConfirmRemark: payload.reconciliationConfirmRemark || '',
    reconciliationLogs: Array.isArray(payload.reconciliationLogs) ? payload.reconciliationLogs : [],
    nextStepReadiness,
    linkedInvoicePrepareNo: clean(payload.linkedInvoicePrepareNo),
    linkedInvoicePrepareId: clean(payload.linkedInvoicePrepareId),
    invoicePrepareGeneratedAt: payload.invoicePrepareGeneratedAt || '',
    invoicePrepareGeneratedBy: payload.invoicePrepareGeneratedBy || '',
    isDemoChain: Boolean(payload.isDemoChain),
    demoChainVersion: clean(payload.demoChainVersion),
    demoChainGeneratedAt: clean(payload.demoChainGeneratedAt),
    demoChainPurpose: clean(payload.demoChainPurpose),
    downstreamActionCode: clean(payload.downstreamActionCode),
    downstreamObjectType: clean(payload.downstreamObjectType),
    downstreamObjectNo: clean(payload.downstreamObjectNo),
    downstreamObjectId: clean(payload.downstreamObjectId),
    downstreamGeneratedAt: clean(payload.downstreamGeneratedAt),
    flowWritebackStatus: clean(payload.flowWritebackStatus),
    nextStepReleaseStatus: clean(payload.nextStepReleaseStatus),
    sourceObjectType: clean(payload.sourceObjectType),
    sourceObjectNo: clean(payload.sourceObjectNo),
    sourceObjectId: clean(payload.sourceObjectId),
    sourceBusinessRoute: clean(payload.sourceBusinessRoute),
    createdFromActionCode: clean(payload.createdFromActionCode),
    sourceLinkStatus: clean(payload.sourceLinkStatus),
    sourceKey: payload.sourceKey || buildSourceKey(payload),
    createdAt: payload.createdAt || nowText(),
    createdBy: payload.createdBy || 'system',
    updatedAt: payload.updatedAt || nowText(),
    logs: Array.isArray(payload.logs) ? payload.logs : [{
      action: TEXT.draftLog,
      operator: payload.createdBy || 'system',
      time: payload.createdAt || nowText(),
      remark: TEXT.draftRemark,
    }],
  }
}

function defaultState() {
  return { supplierSettlements: [] }
}

function normalizeState(raw = {}) {
  return { supplierSettlements: (raw.supplierSettlements || []).map(settlementRecord) }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    return defaultState()
  }
}

const state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export function listSupplierSettlements() {
  return clone(state.supplierSettlements)
}

export function getSupplierSettlementState() {
  return clone(state)
}

export function saveSupplierSettlementState(nextState) {
  state.supplierSettlements = (nextState?.supplierSettlements || []).map(settlementRecord)
  persist()
  return getSupplierSettlementState()
}

export function resetSupplierSettlementState() {
  state.supplierSettlements = []
  persist()
  return getSupplierSettlementState()
}

export function buildSupplierSettlementSourceRows() {
  const scm = getScmState()
  const orders = scm.purchaseOrders || []
  const receives = listPurchaseReceives()
  const inspections = listIncomingInspections()
  const transactions = getInventoryTransactions().filter((item) => PURCHASE_INBOUND_TYPES.includes(item.transactionType || item.type))
  const payablePrepares = listPayablePrepares()
  const rows = []
  const handledPurchaseOrders = new Set()

  transactions.forEach((transaction) => {
    const poNo = sourcePoNo(transaction)
    const txNo = inventoryTransactionNo(transaction)
    if (!poNo && !txNo) return
    const inspection = inspections.find((item) => inspectionNo(item) && inspectionNo(item) === (transaction.sourceInspectionNo || inspectionNo(transaction))) || {}
    const receive = receives.find((item) => receiveNo(item) && receiveNo(item) === (transaction.sourceReceiveNo || receiveNo(inspection) || receiveNo(transaction))) || {}
    const order = orders.find((item) => sourcePoNo(item) === poNo || item.purchaseOrderNo === poNo || item.orderNo === poNo) || {}
    const payableMatches = payablePrepares.filter((item) => {
      const payablePoNo = sourcePoNo(item)
      return payablePoNo === poNo ||
        (inspectionNo(item) && inspectionNo(item) === inspectionNo(inspection)) ||
        (receiveNo(item) && receiveNo(item) === receiveNo(receive))
    })
    const supplierId = clean(order.supplierId || transaction.supplierId || receive.supplierId || inspection.supplierId || payableMatches[0]?.supplierId)
    const supplierName = clean(order.supplierName || transaction.supplierName || receive.supplierName || inspection.supplierName || payableMatches[0]?.supplierName || supplierId || TEXT.supplierPending)
    const payablePrepareAmount = payableMatches.reduce((sum, item) => sum + amount(item.totalPayableAmount || item.payableAmount || item.amount), 0)
    const purchaseAmount = amount(order.totalAmount || order.orderAmount || transaction.purchaseAmount)
    const inventoryAmount = amount(transaction.amount || transaction.totalAmount || transaction.inventoryAmount || purchaseAmount)
    const row = {
      supplierId,
      supplierName,
      purchaseOrderNo: poNo || sourcePoNo(order),
      receiveNo: receiveNo(receive) || receiveNo(transaction),
      inspectionNo: inspectionNo(inspection) || inspectionNo(transaction),
      inventoryTransactionNos: toArray(txNo),
      payablePrepareNos: payableMatches.map(payablePrepareNo).filter(Boolean),
      purchaseAmount,
      inventoryAmount,
      payablePrepareAmount,
    }
    row.differenceAmount = amountDifference([row.purchaseAmount, row.inventoryAmount, row.payablePrepareAmount])
    row.reconciliationStatus = resolveReconciliationStatus(row)
    row.differenceReason = buildDifferenceReason(row)
    row.sourceKey = buildSourceKey(row)
    rows.push(row)
    if (row.purchaseOrderNo) handledPurchaseOrders.add(row.purchaseOrderNo)
  })

  orders.forEach((order) => {
    const poNo = sourcePoNo(order) || order.purchaseOrderNo || order.orderNo
    if (!poNo || handledPurchaseOrders.has(poNo)) return
    const payableMatches = payablePrepares.filter((item) => sourcePoNo(item) === poNo)
    const row = {
      supplierId: clean(order.supplierId || payableMatches[0]?.supplierId),
      supplierName: clean(order.supplierName || payableMatches[0]?.supplierName || order.supplierId || TEXT.supplierPending),
      purchaseOrderNo: poNo,
      receiveNo: '',
      inspectionNo: '',
      inventoryTransactionNos: [],
      payablePrepareNos: payableMatches.map(payablePrepareNo).filter(Boolean),
      purchaseAmount: amount(order.totalAmount || order.orderAmount || order.amount),
      inventoryAmount: 0,
      payablePrepareAmount: payableMatches.reduce((sum, item) => sum + amount(item.totalPayableAmount || item.payableAmount || item.amount), 0),
    }
    row.differenceAmount = amountDifference([row.purchaseAmount, row.inventoryAmount, row.payablePrepareAmount])
    row.reconciliationStatus = resolveReconciliationStatus(row)
    row.differenceReason = buildDifferenceReason(row)
    row.sourceKey = buildSourceKey(row)
    rows.push(row)
  })

  return rows
}

export function createSupplierSettlementDraft(sourceRow = {}, operator = 'system') {
  const row = clone(sourceRow)
  const sourceKey = row.sourceKey || buildSourceKey(row)
  const existed = state.supplierSettlements.find((item) => buildSourceKey(item) === sourceKey)
  if (existed) {
    return { success: false, existed: true, message: TEXT.draftExists, settlement: clone(existed) }
  }
  const settlement = settlementRecord({ ...row, createdBy: operator })
  state.supplierSettlements.unshift(settlement)
  persist()
  return { success: true, settlement: clone(settlement), message: TEXT.draftCreated }
}

export function getSupplierSettlementCreateBlockedReason(source = {}) {
  if (!source?.id || !clean(source.payableCheckNo)) return '来源采购应付核对不存在。'
  if (!['checked', 'matched'].includes(clean(source.checkStatus || source.status))) return '来源采购应付核对尚未完成核对。'
  if (roundAmount(source.totalPayableAmount) <= 0) return '来源应付金额无效。'
  if (roundAmount(source.totalCheckedAmount) <= 0) return '来源核对金额无效。'
  if (roundAmount(source.amountDifference) !== 0) return '来源应付金额与核对金额存在差异。'
  if (!clean(source.supplierId) || !clean(source.supplierName)) return '来源供应商不存在。'
  if (!clean(source.sourcePurchaseOrderNo || source.purchaseOrderNo)) return '来源采购订单不存在。'
  const key = buildSourceKey({ sourcePayableCheckId: source.id, sourcePayableCheckNo: source.payableCheckNo })
  if (state.supplierSettlements.some((item) => buildSourceKey(item) === key)) return '当前采购应付核对已生成供应商结算单。'
  return ''
}

export function createSupplierSettlementFromPayableCheck(sourceOrId = {}, operator = 'page-user') {
  const source = typeof sourceOrId === 'object'
    ? listPayableChecks().find((item) => String(item.id) === String(sourceOrId.id) || clean(item.payableCheckNo) === clean(sourceOrId.payableCheckNo))
    : listPayableChecks().find((item) => String(item.id) === String(sourceOrId) || clean(item.payableCheckNo) === clean(sourceOrId))
  const sourcePayableCheckId = clean(source?.id || sourceOrId?.id)
  const sourcePayableCheckNo = clean(source?.payableCheckNo || sourceOrId?.payableCheckNo)
  const existing = state.supplierSettlements.find((item) => (
    (sourcePayableCheckId && clean(item.sourcePayableCheckId) === sourcePayableCheckId)
    || (sourcePayableCheckNo && clean(item.sourcePayableCheckNo || item.sourceObjectNo) === sourcePayableCheckNo)
  ))
  if (existing) {
    const record = clone(existing)
    return { ok: true, status: 'already_exists', supplierSettlementId: record.id, supplierSettlementNo: record.settlementNo, sourcePayableCheckId: record.sourcePayableCheckId, sourcePayableCheckNo: record.sourcePayableCheckNo, sourcePayablePrepareNo: record.sourcePayablePrepareNo, record }
  }
  const blockedReason = getSupplierSettlementCreateBlockedReason(source)
  if (blockedReason) return { ok: false, status: 'blocked', message: blockedReason, sourcePayableCheckId, sourcePayableCheckNo }
  const line = source.lines?.[0] || {}
  const settlement = settlementRecord({
    sourcePayableCheckId: source.id,
    sourcePayableCheckNo: source.payableCheckNo,
    sourcePayablePrepareId: source.sourcePayablePrepareId,
    sourcePayablePrepareNo: source.sourcePayablePrepareNo,
    payablePrepareNos: [source.sourcePayablePrepareNo],
    sourceInventoryTransactionIds: source.sourceInventoryTransactionIds,
    sourceInventoryTransactionNos: source.sourceInventoryTransactionNos,
    inventoryTransactionNos: source.sourceInventoryTransactionNos,
    sourceWarehouseTaskId: source.sourceWarehouseTaskId,
    sourceWarehouseTaskNo: source.sourceWarehouseTaskNo,
    sourceInspectionId: source.sourceInspectionId,
    sourceInspectionNo: source.sourceInspectionNo,
    inspectionNo: source.sourceInspectionNo,
    sourceReceiveId: source.sourceReceiveId,
    sourceReceiveNo: source.sourceReceiveNo,
    receiveNo: source.sourceReceiveNo,
    sourcePurchaseOrderId: source.sourcePurchaseOrderId,
    sourcePurchaseOrderNo: source.sourcePurchaseOrderNo,
    purchaseOrderNo: source.sourcePurchaseOrderNo,
    sourcePriceApprovalNo: source.sourcePriceApprovalNo,
    supplierId: source.supplierId,
    supplierName: source.supplierName,
    materialId: line.materialId,
    materialCode: line.materialCode,
    materialName: line.materialName,
    unit: line.unit,
    settlementQuantity: source.totalCheckedQty,
    unitPrice: line.checkedPrice || line.payablePrice,
    payableAmount: source.totalPayableAmount,
    checkedAmount: source.totalCheckedAmount,
    purchaseAmount: source.totalPayableAmount,
    inventoryAmount: source.totalPayableAmount,
    payablePrepareAmount: source.totalPayableAmount,
    settlementAmount: source.totalCheckedAmount,
    differenceAmount: source.amountDifference,
    reconciliationStatus: 'matched',
    settlementStatus: 'reconciling',
    sourceObjectType: 'payableCheck',
    sourceObjectId: source.id,
    sourceObjectNo: source.payableCheckNo,
    sourceBusinessRoute: '/finance/payable-checks',
    createdFromActionCode: 'generate_supplier_settlement',
    sourceLinkStatus: 'linked',
    sourceKey: buildSourceKey({ sourcePayableCheckId: source.id }),
    lines: source.lines,
    createdBy: operator,
  })
  state.supplierSettlements.unshift(settlement)
  persist()
  const record = clone(settlement)
  return { ok: true, status: 'created', supplierSettlementId: record.id, supplierSettlementNo: record.settlementNo, sourcePayableCheckId: record.sourcePayableCheckId, sourcePayableCheckNo: record.sourcePayableCheckNo, sourcePayablePrepareNo: record.sourcePayablePrepareNo, record }
}

export function recalculateSupplierSettlementDifference(id) {
  return updateSettlement(id, (current) => {
    const differenceAmount = amountDifference([current.purchaseAmount, current.inventoryAmount, current.payablePrepareAmount])
    const reconciliationStatus = resolveReconciliationStatus({ ...current, differenceAmount })
    const base = { ...current, differenceAmount, reconciliationStatus, differenceType: '' }
    const differenceType = resolveDifferenceType(base)
    const differenceConfirmStatus = resolveDifferenceConfirmStatus({ ...base, differenceType })
    const reconciliationConfirmStatus = resolveReconciliationConfirmStatus({ ...base, differenceType, differenceConfirmStatus })
    return {
      ...current,
      differenceAmount,
      reconciliationStatus,
      settlementStatus: reconciliationStatus === 'matched' ? 'reconciling' : 'difference_pending',
      differenceReason: buildDifferenceReason({ ...current, differenceAmount }),
      differenceType,
      differenceTypeText: typeText(differenceType),
      differenceConfirmStatus,
      differenceConfirmStatusText: statusText(supplierSettlementDifferenceConfirmStatuses, differenceConfirmStatus),
      reconciliationConfirmStatus,
      reconciliationConfirmStatusText: statusText(supplierSettlementReconciliationConfirmStatuses, reconciliationConfirmStatus),
      nextStepReadiness: resolveNextStepReadiness({ reconciliationConfirmStatus }),
    }
  }, 'calculate_difference', TEXT.recalc)
}

export function markSupplierSettlementReconciled(id) {
  return updateSettlement(id, (current) => ({
    ...current,
    settlementStatus: 'reconciled',
    reconciliationStatus: 'matched',
    differenceAmount: 0,
    differenceReason: TEXT.manualReconciled,
  }), 'confirm_reconciliation', TEXT.markReconciled)
}

export function markSupplierSettlementDifferencePending(id, reason = TEXT.manualDifferencePending) {
  return updateSettlement(id, (current) => ({
    ...current,
    settlementStatus: 'difference_pending',
    reconciliationStatus: current.reconciliationStatus === 'matched' ? 'amount_difference' : current.reconciliationStatus,
    differenceReason: reason,
  }), 'select_difference_type', TEXT.markDifferencePending)
}

export function closeSupplierSettlement(id) {
  return updateSettlement(id, (current) => ({
    ...current,
    settlementStatus: 'closed',
    differenceConfirmStatus: current.differenceConfirmStatus === 'pending' ? 'closed' : current.differenceConfirmStatus,
  }), 'close_settlement', TEXT.closeSettlement)
}

export function selectSupplierSettlementDifferenceType(id, differenceType, remark = '') {
  const validType = supplierSettlementDifferenceTypes.some((item) => item.value === differenceType) ? differenceType : 'unknown'
  return updateSettlement(id, (current) => {
    const differenceConfirmStatus = validType === 'none' ? 'not_required' : 'pending'
    const reconciliationConfirmStatus = resolveReconciliationConfirmStatus({ ...current, differenceType: validType, differenceConfirmStatus })
    return {
      ...current,
      differenceType: validType,
      differenceTypeText: typeText(validType),
      differenceConfirmStatus,
      differenceConfirmStatusText: statusText(supplierSettlementDifferenceConfirmStatuses, differenceConfirmStatus),
      differenceConfirmRemark: remark || current.differenceConfirmRemark || typeText(validType),
      reconciliationConfirmStatus,
      reconciliationConfirmStatusText: statusText(supplierSettlementReconciliationConfirmStatuses, reconciliationConfirmStatus),
      nextStepReadiness: resolveNextStepReadiness({ reconciliationConfirmStatus }),
    }
  }, 'select_difference_type', remark || TEXT.selectDifferenceType)
}

export function confirmSupplierSettlementDifference(id, remark = '') {
  return updateSettlement(id, (current) => {
    const differenceType = current.differenceType && current.differenceType !== 'none' ? current.differenceType : resolveDifferenceType(current)
    if (differenceType === 'none') {
      return {
        ...current,
        differenceConfirmStatus: 'not_required',
        differenceConfirmStatusText: statusText(supplierSettlementDifferenceConfirmStatuses, 'not_required'),
        reconciliationConfirmStatus: 'ready',
        reconciliationConfirmStatusText: statusText(supplierSettlementReconciliationConfirmStatuses, 'ready'),
      }
    }
    return {
      ...current,
      differenceType,
      differenceTypeText: typeText(differenceType),
      differenceConfirmStatus: 'confirmed',
      differenceConfirmStatusText: statusText(supplierSettlementDifferenceConfirmStatuses, 'confirmed'),
      differenceConfirmRemark: remark || current.differenceConfirmRemark || typeText(differenceType),
      differenceConfirmedBy: 'page-user',
      differenceConfirmedAt: nowText(),
      reconciliationConfirmStatus: 'ready',
      reconciliationConfirmStatusText: statusText(supplierSettlementReconciliationConfirmStatuses, 'ready'),
      nextStepReadiness: 'not_ready',
    }
  }, 'confirm_difference', remark || TEXT.confirmDifference)
}

export function rejectSupplierSettlementDifference(id, remark = '') {
  return updateSettlement(id, (current) => ({
    ...current,
    differenceConfirmStatus: 'rejected',
    differenceConfirmStatusText: statusText(supplierSettlementDifferenceConfirmStatuses, 'rejected'),
    differenceConfirmRemark: remark || TEXT.rejectDifference,
    differenceConfirmedBy: 'page-user',
    differenceConfirmedAt: nowText(),
    reconciliationConfirmStatus: 'blocked',
    reconciliationConfirmStatusText: statusText(supplierSettlementReconciliationConfirmStatuses, 'blocked'),
    nextStepReadiness: 'not_ready',
  }), 'reject_difference', remark || TEXT.rejectDifference)
}

export function confirmSupplierSettlementReconciliation(id, remark = '') {
  const current = state.supplierSettlements.find((item) => String(item.id) === String(id))
  if (!current) return { success: false, message: TEXT.notFound }
  const differenceConfirmStatus = current.differenceConfirmStatus || resolveDifferenceConfirmStatus(current)
  if (!['not_required', 'confirmed'].includes(differenceConfirmStatus)) {
    return { success: false, blocked: true, message: TEXT.reconciliationBlocked, settlement: clone(current) }
  }
  return updateSettlement(id, (row) => ({
    ...row,
    reconciliationConfirmStatus: 'confirmed',
    reconciliationConfirmStatusText: statusText(supplierSettlementReconciliationConfirmStatuses, 'confirmed'),
    reconciliationConfirmedBy: 'page-user',
    reconciliationConfirmedAt: nowText(),
    reconciliationConfirmRemark: remark || TEXT.reconciliationReady,
    settlementStatus: 'reconciled',
    reconciliationStatus: row.differenceConfirmStatus === 'confirmed' ? 'amount_difference_confirmed' : 'matched',
    nextStepReadiness: 'ready_for_invoice_prepare',
  }), 'confirm_reconciliation', remark || TEXT.confirmReconciliation)
}

export function linkSupplierSettlementInvoicePrepare(id, invoicePrepare = {}, operator = 'page-user') {
  const current = state.supplierSettlements.find((item) => String(item.id) === String(id))
  if (!current) return { success: false, message: TEXT.notFound }
  if (current.linkedInvoicePrepareId || current.linkedInvoicePrepareNo) {
    return { success: false, existed: true, message: '\u5df2\u751f\u6210\u53d1\u7968\u51c6\u5907', settlement: clone(current) }
  }
  return updateSettlement(id, (row) => ({
    ...row,
    linkedInvoicePrepareId: invoicePrepare.id || invoicePrepare.invoicePrepareId || '',
    linkedInvoicePrepareNo: invoicePrepare.invoicePrepareNo || '',
    invoicePrepareGeneratedAt: nowText(),
    invoicePrepareGeneratedBy: operator,
  }), 'link_invoice_prepare', '\u5173\u8054\u91c7\u8d2d\u53d1\u7968\u51c6\u5907\uff0c\u4ec5\u56de\u5199\u4f9b\u5e94\u5546\u7ed3\u7b97\u94fe\u63a5\u5b57\u6bb5')
}

function updateSettlement(id, updater, action, remark = '') {
  const index = state.supplierSettlements.findIndex((item) => String(item.id) === String(id))
  if (index < 0) return { success: false, message: TEXT.notFound }
  const current = state.supplierSettlements[index]
  const beforeStatus = `${current.differenceConfirmStatus || ''}/${current.reconciliationConfirmStatus || ''}`
  const updated = updater(current)
  const next = settlementRecord({
    ...updated,
    id: current.id,
    settlementNo: current.settlementNo,
    createdAt: current.createdAt,
    createdBy: current.createdBy,
    logs: [
      ...(current.logs || []),
      { action: remark || action, operator: 'system', time: nowText(), remark: remark || action },
    ],
    reconciliationLogs: [
      ...(current.reconciliationLogs || []),
      logEntry(action, beforeStatus, `${updated.differenceConfirmStatus || ''}/${updated.reconciliationConfirmStatus || ''}`, remark || action, updated),
    ],
    updatedAt: nowText(),
  })
  state.supplierSettlements.splice(index, 1, next)
  persist()
  return { success: true, settlement: clone(next), message: action }
}
