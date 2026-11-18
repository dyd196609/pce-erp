import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  getPayableCheckById,
  listPayableChecks,
  markPayableCheckInvoicePrepared,
} from './payableCheckStore.js'
import {
  linkSupplierSettlementInvoicePrepare,
  listSupplierSettlements,
} from '../scm/supplierSettlementStore.js'

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

function unique(values = []) {
  return [...new Set((values || []).filter(Boolean).map((item) => String(item)))]
}

function sourceNoList(value) {
  if (Array.isArray(value)) return unique(value)
  if (!value) return []
  return unique(String(value).split(/[,\s、，]+/))
}

function amountMatches(left, right) {
  return Math.abs(roundAmount(left) - roundAmount(right)) < 0.01
}

function taxSplitFromNet(invoiceAmount, taxRate = DEFAULT_TAX_RATE) {
  const amount = roundAmount(invoiceAmount)
  const taxAmount = roundAmount(amount * toNumber(taxRate) / 100)
  return { invoiceAmount: amount, taxAmount, totalInvoiceAmount: roundAmount(amount + taxAmount) }
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
    sourceSettlementId: payload.sourceSettlementId || '',
    sourceSettlementNo: payload.sourceSettlementNo || '',
    sourceInventoryTransactionIds: payload.sourceInventoryTransactionIds || [],
    sourceInventoryTransactionNos: sourceNoList(payload.sourceInventoryTransactionNos),
    inventoryTransactionNos: sourceNoList(payload.inventoryTransactionNos || payload.sourceInventoryTransactionNos),
    payablePrepareNos: sourceNoList(payload.payablePrepareNos || payload.sourcePayablePrepareNo),
    supplierId: payload.supplierId || '',
    supplierName: payload.supplierName || '',
    buyerId: payload.buyerId || '',
    buyerName: payload.buyerName || '',
    sourcePurchaseOrderNo: payload.sourcePurchaseOrderNo || '',
    purchaseOrderNo: payload.purchaseOrderNo || payload.sourcePurchaseOrderNo || '',
    sourceReceiveNo: payload.sourceReceiveNo || '',
    receiveNo: payload.receiveNo || payload.sourceReceiveNo || '',
    sourceInspectionNo: payload.sourceInspectionNo || '',
    inspectionNo: payload.inspectionNo || payload.sourceInspectionNo || '',
    rootRequestNo: payload.rootRequestNo || '',
    invoicePrepareStatus: payload.invoicePrepareStatus || 'prepared',
    invoiceStatus: payload.invoiceStatus || 'not_received',
    expectedInvoiceDate: payload.expectedInvoiceDate || today(),
    invoiceType: payload.invoiceType || 'specialVat',
    taxRate,
    settlementAmount: roundAmount(payload.settlementAmount ?? payload.totalInvoiceAmount ?? summary.totalInvoiceAmount),
    invoiceAmount: roundAmount(payload.invoiceAmount ?? payload.totalInvoiceAmount ?? summary.totalInvoiceAmount),
    taxAmount: roundAmount(payload.taxAmount ?? payload.totalTaxAmount ?? summary.totalTaxAmount),
    sourceReconciliationStatus: payload.sourceReconciliationStatus || '',
    sourceDifferenceType: payload.sourceDifferenceType || '',
    sourceDifferenceConfirmStatus: payload.sourceDifferenceConfirmStatus || '',
    sourceNextStepReadiness: payload.sourceNextStepReadiness || '',
    totalNoTaxAmount: roundAmount(payload.totalNoTaxAmount ?? summary.totalNoTaxAmount),
    totalTaxAmount: roundAmount(payload.totalTaxAmount ?? summary.totalTaxAmount),
    totalInvoiceAmount: roundAmount(payload.totalInvoiceAmount ?? summary.totalInvoiceAmount),
    invoiceNo: payload.invoiceNo || '',
    invoiceDate: payload.invoiceDate || '',
    invoiceReceived: payload.invoiceReceived ?? false,
    invoiceReceivedDate: payload.invoiceReceivedDate || '',
    invoiceMatchStatus: payload.invoiceMatchStatus || 'unmatched',
    differenceReason: payload.differenceReason || '',
    invoicePrepareRemark: payload.invoicePrepareRemark || payload.remark || '',
    apDraftGenerated: payload.apDraftGenerated ?? false,
    targetApDraftId: payload.targetApDraftId || '',
    targetApDraftNo: payload.targetApDraftNo || '',
    targetModule: payload.targetModule || '',
    apDraftGeneratedAt: payload.apDraftGeneratedAt || '',
    linkedPayableConfirmId: payload.linkedPayableConfirmId || '',
    linkedPayableConfirmNo: payload.linkedPayableConfirmNo || '',
    payableConfirmGeneratedAt: payload.payableConfirmGeneratedAt || '',
    payableConfirmGeneratedBy: payload.payableConfirmGeneratedBy || '',
    isDemoChain: Boolean(payload.isDemoChain),
    demoChainVersion: payload.demoChainVersion || '',
    demoChainGeneratedAt: payload.demoChainGeneratedAt || '',
    demoChainPurpose: payload.demoChainPurpose || '',
    remark: payload.remark || '',
    logs: Array.isArray(payload.logs) ? payload.logs : [],
    lines,
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

function appendPrepareLog(current, action, beforeStatus, afterStatus, remark = '', operator = 'page-user') {
  current.logs = [
    ...(current.logs || []),
    {
      action,
      beforeStatus,
      afterStatus,
      operator,
      time: nowText(),
      remark: remark || action,
      sourceSettlementNo: current.sourceSettlementNo || '',
      invoicePrepareNo: current.invoicePrepareNo || '',
    },
  ]
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

export function linkInvoicePreparePayableConfirm(id, payableConfirm = {}, operator = 'page-user') {
  const current = byId(state.invoicePrepares, id)
  if (!current) return { success: false, error: '未找到采购发票准备记录。' }
  const beforeStatus = `${current.invoicePrepareStatus || ''}/${current.invoiceStatus || ''}`
  current.linkedPayableConfirmId = payableConfirm.id || payableConfirm.payableConfirmId || current.linkedPayableConfirmId || ''
  current.linkedPayableConfirmNo = payableConfirm.payableConfirmNo || current.linkedPayableConfirmNo || ''
  current.payableConfirmGeneratedAt = current.payableConfirmGeneratedAt || nowText()
  current.payableConfirmGeneratedBy = operator
  current.updatedAt = nowText()
  appendPrepareLog(current, 'link_payable_confirm_prepare', beforeStatus, `${current.invoicePrepareStatus}/${current.invoiceStatus}`, `已关联应付确认准备 ${current.linkedPayableConfirmNo || '-'}`, operator)
  persist()
  writeInvoicePrepareLog('link_payable_confirm_prepare', {
    sourceNo: current.invoicePrepareNo,
    targetId: current.linkedPayableConfirmId,
    targetNo: current.linkedPayableConfirmNo,
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

export function isInvoicePrepareGeneratedFromSettlement(settlementOrId) {
  const settlement = typeof settlementOrId === 'object'
    ? settlementOrId
    : listSupplierSettlements().find((item) => String(item.id) === String(settlementOrId))
  if (!settlement?.id) return false
  return Boolean(
    settlement.linkedInvoicePrepareId ||
    settlement.linkedInvoicePrepareNo ||
    state.invoicePrepares.some((prepare) => String(prepare.sourceSettlementId) === String(settlement.id)),
  )
}

export function canCreateInvoicePrepareFromSettlement(settlement = {}) {
  if (!settlement?.id) return { canCreate: false, reason: '未找到供应商结算记录。' }
  if (isInvoicePrepareGeneratedFromSettlement(settlement)) return { canCreate: false, reason: '已存在结算记录对应的发票准备。' }
  if (settlement.settlementStatus === 'closed') return { canCreate: false, reason: '结算已关闭，不能生成发票准备。' }
  if (settlement.settlementStatus !== 'reconciled') return { canCreate: false, reason: '结算状态未达到已对账。' }
  if (settlement.reconciliationConfirmStatus !== 'confirmed') return { canCreate: false, reason: '对账尚未确认。' }
  if (settlement.nextStepReadiness !== 'ready_for_invoice_prepare') return { canCreate: false, reason: '下一步标识未达到可进入发票准备。' }
  if (!['not_required', 'confirmed'].includes(settlement.differenceConfirmStatus)) return { canCreate: false, reason: '差异原因尚未确认。' }
  if (!toNumber(settlement.settlementAmount)) return { canCreate: false, reason: '结算金额为空，不能生成发票准备。' }
  return { canCreate: true, reason: '' }
}

export function getInvoicePrepareSourcesFromSupplierSettlements() {
  return listSupplierSettlements().map((settlement) => {
    const generated = isInvoicePrepareGeneratedFromSettlement(settlement)
    const result = canCreateInvoicePrepareFromSettlement(settlement)
    return {
      ...settlement,
      invoicePrepareGenerated: generated,
      invoicePrepareGeneratedText: generated ? '已生成发票准备' : '未生成',
      canCreateInvoicePrepare: result.canCreate,
      sourceRejectReason: result.reason,
    }
  })
}

function buildLineFromSettlement(settlement = {}, taxRate = DEFAULT_TAX_RATE) {
  const split = taxSplitFromNet(settlement.settlementAmount, taxRate)
  return normalizeLine({
    lineNo: 1,
    materialCode: 'SETTLEMENT',
    materialName: '供应商结算金额',
    unit: '项',
    checkedQty: 1,
    checkedPrice: settlement.settlementAmount,
    checkedAmount: settlement.settlementAmount,
    noTaxAmount: split.invoiceAmount,
    taxRate,
    taxAmount: split.taxAmount,
    invoiceAmount: split.totalInvoiceAmount,
    sourcePurchaseOrderNo: settlement.purchaseOrderNo,
    sourceReceiveNo: settlement.receiveNo,
    sourceInspectionNo: settlement.inspectionNo,
    remark: '由供应商结算生成发票准备明细，仅用于发票准备。',
  }, 0, taxRate)
}

export function createInvoicePrepareFromSupplierSettlement(settlementId, operator = 'page-user') {
  const settlement = listSupplierSettlements().find((item) => String(item.id) === String(settlementId))
  const check = canCreateInvoicePrepareFromSettlement(settlement)
  if (!check.canCreate) {
    writeInvoicePrepareLog('create_from_settlement_blocked', {
      sourceNo: settlement?.settlementNo || settlementId,
      targetId: settlementId,
      result: check.reason,
    })
    return { success: false, error: check.reason, settlement }
  }
  const taxRate = DEFAULT_TAX_RATE
  const split = taxSplitFromNet(settlement.settlementAmount, taxRate)
  const prepare = invoicePrepare({
    sourceSettlementId: settlement.id,
    sourceSettlementNo: settlement.settlementNo,
    supplierId: settlement.supplierId,
    supplierName: settlement.supplierName,
    sourcePurchaseOrderNo: settlement.purchaseOrderNo,
    purchaseOrderNo: settlement.purchaseOrderNo,
    sourceReceiveNo: settlement.receiveNo,
    receiveNo: settlement.receiveNo,
    sourceInspectionNo: settlement.inspectionNo,
    inspectionNo: settlement.inspectionNo,
    inventoryTransactionNos: settlement.inventoryTransactionNos,
    sourceInventoryTransactionNos: settlement.inventoryTransactionNos,
    payablePrepareNos: settlement.payablePrepareNos,
    sourcePayablePrepareNo: (settlement.payablePrepareNos || []).join('、'),
    settlementAmount: settlement.settlementAmount,
    invoiceAmount: split.invoiceAmount,
    taxRate,
    taxAmount: split.taxAmount,
    totalInvoiceAmount: split.totalInvoiceAmount,
    invoicePrepareStatus: 'draft',
    invoiceStatus: 'not_received',
    sourceReconciliationStatus: settlement.reconciliationStatus,
    sourceDifferenceType: settlement.differenceType,
    sourceDifferenceConfirmStatus: settlement.differenceConfirmStatus,
    sourceNextStepReadiness: settlement.nextStepReadiness,
    invoicePrepareRemark: '由供应商结算生成，仅做采购发票准备，不生成正式发票、应付、付款、总账、核销或银行流水。',
    remark: '由供应商结算生成，仅做采购发票准备。',
    lines: [buildLineFromSettlement(settlement, taxRate)],
    createdBy: operator,
  })
  appendPrepareLog(prepare, 'create_from_settlement', '', prepare.invoicePrepareStatus, '由供应商结算生成采购发票准备。', operator)
  state.invoicePrepares.unshift(prepare)
  persist()
  const writeBack = linkSupplierSettlementInvoicePrepare(settlement.id, prepare, operator)
  writeInvoicePrepareLog('create_from_settlement', {
    sourceNo: settlement.settlementNo,
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

export function inputPurchaseInvoiceInfo(id, info = {}, operator = 'page-user') {
  const current = byId(state.invoicePrepares, id)
  if (!current) return { success: false, error: '未找到发票准备记录。' }
  if (['closed', 'cancelled', 'apDraftGenerated'].includes(current.invoicePrepareStatus)) return { success: false, error: '当前发票准备已关闭或已流转，不能录入发票信息。' }
  const beforeStatus = `${current.invoicePrepareStatus || ''}/${current.invoiceStatus || ''}`
  const invoiceAmount = roundAmount(info.invoiceAmount ?? current.invoiceAmount ?? current.settlementAmount)
  const taxRate = toNumber(info.taxRate ?? current.taxRate ?? DEFAULT_TAX_RATE)
  const taxAmount = roundAmount(info.taxAmount ?? invoiceAmount * taxRate / 100)
  const totalInvoiceAmount = roundAmount(info.totalInvoiceAmount ?? invoiceAmount + taxAmount)
  Object.assign(current, invoicePrepare({
    ...current,
    invoiceNo: info.invoiceNo ?? current.invoiceNo,
    invoiceDate: info.invoiceDate ?? current.invoiceDate,
    invoiceType: info.invoiceType ?? current.invoiceType,
    invoiceAmount,
    taxRate,
    taxAmount,
    totalInvoiceAmount,
    totalNoTaxAmount: invoiceAmount,
    totalTaxAmount: taxAmount,
    invoicePrepareRemark: info.invoicePrepareRemark ?? info.remark ?? current.invoicePrepareRemark,
    remark: info.invoicePrepareRemark ?? info.remark ?? current.remark,
    differenceReason: amountMatches(invoiceAmount, current.settlementAmount)
      ? current.differenceReason
      : (info.invoicePrepareRemark || info.remark || '发票金额与结算金额存在差异，待人工核对。'),
    invoicePrepareStatus: amountMatches(invoiceAmount, current.settlementAmount) ? current.invoicePrepareStatus : 'received_pending_check',
    invoiceStatus: current.invoiceStatus === 'not_received' ? 'received_pending_check' : current.invoiceStatus,
    updatedAt: nowText(),
  }))
  appendPrepareLog(current, 'input_invoice_info', beforeStatus, `${current.invoicePrepareStatus}/${current.invoiceStatus}`, info.invoicePrepareRemark || info.remark || '录入发票信息。', operator)
  persist()
  writeInvoicePrepareLog('input_invoice_info', { targetId: current.id, targetNo: current.invoicePrepareNo })
  return { success: true, invoicePrepare: clone(current) }
}

export function markPurchaseInvoiceReceived(id, operator = 'page-user') {
  const current = byId(state.invoicePrepares, id)
  if (!current) return { success: false, error: '未找到发票准备记录。' }
  if (['closed', 'cancelled', 'apDraftGenerated'].includes(current.invoicePrepareStatus)) return { success: false, error: '当前发票准备不能继续收票。' }
  const beforeStatus = `${current.invoicePrepareStatus || ''}/${current.invoiceStatus || ''}`
  current.invoiceStatus = 'received_pending_check'
  current.invoicePrepareStatus = current.invoicePrepareStatus === 'draft' ? 'waiting_invoice' : 'invoice_received'
  current.invoiceReceived = true
  current.invoiceReceivedDate = current.invoiceReceivedDate || today()
  current.updatedAt = nowText()
  appendPrepareLog(current, 'mark_invoice_received', beforeStatus, `${current.invoicePrepareStatus}/${current.invoiceStatus}`, '登记已收到发票，等待核对。', operator)
  persist()
  writeInvoicePrepareLog('mark_invoice_received', { targetId: current.id, targetNo: current.invoicePrepareNo })
  return { success: true, invoicePrepare: clone(current) }
}

export function markPurchaseInvoiceChecked(id, operator = 'page-user') {
  const current = byId(state.invoicePrepares, id)
  if (!current) return { success: false, error: '未找到发票准备记录。' }
  if (!current.invoiceNo || !current.invoiceDate) return { success: false, error: '请先录入发票号码和发票日期。' }
  const amountOk = amountMatches(current.invoiceAmount, current.settlementAmount)
  if (!amountOk && !current.invoicePrepareRemark && !current.differenceReason) return { success: false, error: '发票金额与结算金额不一致，请先填写核对说明。' }
  const beforeStatus = `${current.invoicePrepareStatus || ''}/${current.invoiceStatus || ''}`
  current.invoiceStatus = 'checked'
  current.invoicePrepareStatus = 'checked'
  current.invoiceMatchStatus = amountOk ? 'matched' : 'difference_confirmed'
  current.updatedAt = nowText()
  appendPrepareLog(current, 'check_invoice_passed', beforeStatus, `${current.invoicePrepareStatus}/${current.invoiceStatus}`, amountOk ? '发票金额与结算金额一致。' : '发票金额存在差异但已有说明，仅完成发票准备核对。', operator)
  persist()
  writeInvoicePrepareLog('check_invoice_passed', { targetId: current.id, targetNo: current.invoicePrepareNo })
  return { success: true, invoicePrepare: clone(current) }
}

export function markPurchaseInvoiceAbnormal(id, remark = '发票异常，待人工处理。', operator = 'page-user') {
  const current = byId(state.invoicePrepares, id)
  if (!current) return { success: false, error: '未找到发票准备记录。' }
  const beforeStatus = `${current.invoicePrepareStatus || ''}/${current.invoiceStatus || ''}`
  current.invoiceStatus = 'rejected'
  current.invoicePrepareStatus = 'blocked'
  current.differenceReason = remark
  current.updatedAt = nowText()
  appendPrepareLog(current, 'mark_invoice_abnormal', beforeStatus, `${current.invoicePrepareStatus}/${current.invoiceStatus}`, remark, operator)
  persist()
  writeInvoicePrepareLog('mark_invoice_abnormal', { targetId: current.id, targetNo: current.invoicePrepareNo, result: remark })
  return { success: true, invoicePrepare: clone(current) }
}

export function closePurchaseInvoicePrepare(id, remark = '关闭发票准备。', operator = 'page-user') {
  const current = byId(state.invoicePrepares, id)
  if (!current) return { success: false, error: '未找到发票准备记录。' }
  const beforeStatus = `${current.invoicePrepareStatus || ''}/${current.invoiceStatus || ''}`
  current.invoicePrepareStatus = 'closed'
  current.updatedAt = nowText()
  appendPrepareLog(current, 'close_invoice_prepare', beforeStatus, `${current.invoicePrepareStatus}/${current.invoiceStatus || ''}`, remark, operator)
  persist()
  writeInvoicePrepareLog('close_invoice_prepare', { targetId: current.id, targetNo: current.invoicePrepareNo, result: remark })
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
