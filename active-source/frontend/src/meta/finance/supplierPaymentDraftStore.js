import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import { getAccountPayableDraftById, listAccountPayableDrafts, markApDraftPaymentDraftGenerated } from './accountPayableDraftStore.js'

const STORAGE_KEY = 'supplier-payment-draft-state-v1'
const SOURCE_READY_STATUSES = ['paymentPending', 'confirmed']
const ACTIVE_PAYMENT_DRAFT_STATUSES = ['draft', 'submitted', 'approved', 'paymentReady']

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
  return { supplierPaymentDrafts: [] }
}

function byId(collection, id) {
  return (collection || []).find((item) => String(item.id) === String(id)) || null
}

function amountParts(totalValue, paidValue) {
  const totalPayableAmount = roundAmount(totalValue)
  const paidAmount = roundAmount(paidValue)
  const unpaidAmount = roundAmount(Math.max(totalPayableAmount - paidAmount, 0))
  return { totalPayableAmount, paidAmount, unpaidAmount, applyPayAmount: unpaidAmount }
}

function normalizeLine(line = {}, index = 0) {
  const payableAmount = roundAmount(line.payableAmount ?? line.invoiceAmount)
  const paidAmount = roundAmount(line.paidAmount ?? 0)
  const unpaidAmount = roundAmount(line.unpaidAmount ?? Math.max(payableAmount - paidAmount, 0))
  const applyPayAmount = roundAmount(line.applyPayAmount ?? unpaidAmount)
  return {
    id: line.id || createId('spdl'),
    lineNo: line.lineNo || index + 1,
    sourceApDraftLineId: line.sourceApDraftLineId || line.id || '',
    materialId: line.materialId || '',
    materialCode: line.materialCode || '',
    materialName: line.materialName || '',
    spec: line.spec || line.specification || '',
    unit: line.unit || '',
    payableAmount,
    paidAmount,
    unpaidAmount,
    applyPayAmount: Math.min(Math.max(applyPayAmount, 0), unpaidAmount),
    sourcePurchaseOrderNo: line.sourcePurchaseOrderNo || '',
    sourceReceiveNo: line.sourceReceiveNo || '',
    sourceInspectionNo: line.sourceInspectionNo || '',
    sourceInventoryTransactionId: line.sourceInventoryTransactionId || '',
    sourceInventoryTransactionNo: line.sourceInventoryTransactionNo || '',
    rootRequestNo: line.rootRequestNo || '',
    remark: line.remark || '',
  }
}

function supplierPaymentDraft(payload = {}) {
  const stamp = nowText()
  const lines = (payload.lines || []).map(normalizeLine)
  const parts = amountParts(payload.totalPayableAmount, payload.paidAmount)
  const unpaidAmount = roundAmount(payload.unpaidAmount ?? parts.unpaidAmount)
  const applyPayAmount = roundAmount(payload.applyPayAmount ?? unpaidAmount)
  return {
    id: payload.id || createId('spd'),
    paymentDraftNo: payload.paymentDraftNo || createNo('SPD'),
    sourceApDraftId: payload.sourceApDraftId || '',
    sourceApDraftNo: payload.sourceApDraftNo || '',
    sourceInvoicePrepareNo: payload.sourceInvoicePrepareNo || '',
    sourcePayableCheckNo: payload.sourcePayableCheckNo || '',
    sourcePayablePrepareNo: payload.sourcePayablePrepareNo || '',
    sourceInventoryTransactionIds: payload.sourceInventoryTransactionIds || [],
    sourceInventoryTransactionNos: payload.sourceInventoryTransactionNos || [],
    supplierId: payload.supplierId || '',
    supplierName: payload.supplierName || '',
    sourcePurchaseOrderNo: payload.sourcePurchaseOrderNo || '',
    sourceReceiveNo: payload.sourceReceiveNo || '',
    sourceInspectionNo: payload.sourceInspectionNo || '',
    rootRequestNo: payload.rootRequestNo || '',
    paymentDraftStatus: payload.paymentDraftStatus || 'draft',
    applyDate: payload.applyDate || today(),
    expectedPayDate: payload.expectedPayDate || payload.dueDate || '',
    dueDate: payload.dueDate || payload.expectedPayDate || '',
    totalPayableAmount: roundAmount(payload.totalPayableAmount ?? parts.totalPayableAmount),
    paidAmount: roundAmount(payload.paidAmount ?? parts.paidAmount),
    unpaidAmount,
    applyPayAmount: Math.min(Math.max(applyPayAmount, 0), unpaidAmount),
    paymentMethod: payload.paymentMethod || 'bankTransfer',
    paymentAccount: payload.paymentAccount || '',
    supplierBankName: payload.supplierBankName || '',
    supplierBankAccount: payload.supplierBankAccount || '',
    paymentReason: payload.paymentReason || '采购应付账款到期付款申请预备',
    paymentRemark: payload.paymentRemark || '',
    approvalStatus: payload.approvalStatus || 'draft',
    paymentStatus: payload.paymentStatus || 'unpaid',
    voucherStatus: payload.voucherStatus || 'notGenerated',
    paymentReady: payload.paymentReady ?? false,
    voucherReady: payload.voucherReady ?? false,
    paymentPrepareGenerated: payload.paymentPrepareGenerated ?? false,
    targetPaymentPrepareId: payload.targetPaymentPrepareId || '',
    targetPaymentPrepareNo: payload.targetPaymentPrepareNo || '',
    paymentPrepareGeneratedAt: payload.paymentPrepareGeneratedAt || '',
    lines,
    createdAt: payload.createdAt || stamp,
    updatedAt: payload.updatedAt || stamp,
  }
}

function normalizeState(raw = {}) {
  return { supplierPaymentDrafts: (raw.supplierPaymentDrafts || []).map(supplierPaymentDraft) }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[SUPPLIER PAYMENT DRAFT STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export function writePaymentDraftLog(action, payload = {}) {
  addOperationLog({
    module: '供应商付款草稿',
    action,
    targetType: payload.targetType || 'supplierPaymentDraft',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源单据：${payload.sourceNo || '-'}`,
      `目标单据：${payload.targetNo || '-'}`,
      `结果：${payload.result || '成功'}`,
    ].join('；'),
  })
}

export function getSupplierPaymentDraftState() {
  return clone(state)
}

export function saveSupplierPaymentDraftState(nextState) {
  state = normalizeState(nextState)
  persist()
  writePaymentDraftLog('保存供应商付款草稿状态', { targetType: 'supplierPaymentDraftState', targetId: 'state' })
  return getSupplierPaymentDraftState()
}

export function resetSupplierPaymentDraftState() {
  state = defaultState()
  persist()
  writePaymentDraftLog('恢复供应商付款草稿演示数据', { targetType: 'supplierPaymentDraftState', targetId: 'demo' })
  return getSupplierPaymentDraftState()
}

export function listSupplierPaymentDrafts() {
  return clone(state.supplierPaymentDrafts)
}

export function getSupplierPaymentDraftById(id) {
  return clone(byId(state.supplierPaymentDrafts, id))
}

export function markPaymentDraftPrepareGenerated(id, paymentPrepare = {}) {
  const current = byId(state.supplierPaymentDrafts, id)
  if (!current) return { success: false, error: '未找到供应商付款草稿。' }
  Object.assign(current, {
    paymentPrepareGenerated: true,
    targetPaymentPrepareId: paymentPrepare.id || paymentPrepare.paymentPrepareId || current.targetPaymentPrepareId || '',
    targetPaymentPrepareNo: paymentPrepare.paymentPrepareNo || current.targetPaymentPrepareNo || '',
    paymentPrepareGeneratedAt: current.paymentPrepareGeneratedAt || nowText(),
    updatedAt: nowText(),
  })
  persist()
  writePaymentDraftLog('生成正式付款单预备成功后回写供应商付款草稿状态', {
    sourceNo: current.paymentDraftNo,
    targetId: current.targetPaymentPrepareId,
    targetNo: current.targetPaymentPrepareNo,
  })
  return { success: true, supplierPaymentDraft: clone(current) }
}

export function isPaymentDraftGenerated(apDraftOrId) {
  const apDraft = typeof apDraftOrId === 'object' ? apDraftOrId : getAccountPayableDraftById(apDraftOrId)
  if (!apDraft?.id) return false
  const activeDraft = state.supplierPaymentDrafts.find((draft) => (
    String(draft.sourceApDraftId) === String(apDraft.id)
    && ACTIVE_PAYMENT_DRAFT_STATUSES.includes(draft.paymentDraftStatus)
  ))
  if (activeDraft) return true
  const targetDraft = state.supplierPaymentDrafts.find((draft) => (
    (apDraft.targetPaymentDraftId && String(draft.id) === String(apDraft.targetPaymentDraftId))
    || (apDraft.targetPaymentDraftNo && String(draft.paymentDraftNo) === String(apDraft.targetPaymentDraftNo))
  ))
  if (targetDraft) return ACTIVE_PAYMENT_DRAFT_STATUSES.includes(targetDraft.paymentDraftStatus)
  return Boolean(apDraft.paymentDraftGenerated || apDraft.targetPaymentDraftId || apDraft.targetPaymentDraftNo)
}

function sourceRejectReason(apDraft = {}) {
  if (!apDraft?.id) return '未找到应付账款草稿。'
  if (isPaymentDraftGenerated(apDraft)) {
    writePaymentDraftLog('拦截重复生成供应商付款草稿', {
      sourceNo: apDraft.apDraftNo,
      targetId: apDraft.targetPaymentDraftId || apDraft.id,
      targetNo: apDraft.targetPaymentDraftNo || '',
      result: '该应付账款草稿已生成供应商付款草稿，不能重复生成。',
    })
    return '该应付账款草稿已生成供应商付款草稿，不能重复生成。'
  }
  if (!SOURCE_READY_STATUSES.includes(apDraft.apStatus)) return '只有 paymentPending 或 confirmed 状态的应付账款草稿可生成供应商付款草稿。'
  const totalPayableAmount = roundAmount(apDraft.totalPayableAmount)
  const paidAmount = roundAmount(apDraft.paidAmount ?? 0)
  const unpaidAmount = roundAmount(apDraft.unpaidAmount ?? totalPayableAmount - paidAmount)
  if (paidAmount >= totalPayableAmount || unpaidAmount <= 0) return '该应付账款草稿未付款金额为 0，不能生成供应商付款草稿。'
  return ''
}

export function getPaymentDraftSourcesFromApDrafts() {
  return listAccountPayableDrafts().map((apDraft) => {
    const totalPayableAmount = roundAmount(apDraft.totalPayableAmount)
    const paidAmount = roundAmount(apDraft.paidAmount ?? 0)
    const unpaidAmount = roundAmount(apDraft.unpaidAmount ?? totalPayableAmount - paidAmount)
    const generated = isPaymentDraftGenerated(apDraft)
    const existed = state.supplierPaymentDrafts.find((draft) => (
      String(draft.sourceApDraftId) === String(apDraft.id)
      && ACTIVE_PAYMENT_DRAFT_STATUSES.includes(draft.paymentDraftStatus)
    ))
    if (generated && existed && !apDraft.paymentDraftGenerated && !apDraft.targetPaymentDraftNo) {
      writePaymentDraftLog('历史数据兼容识别已生成供应商付款草稿', {
        sourceNo: apDraft.apDraftNo,
        targetId: existed.id,
        targetNo: existed.paymentDraftNo,
      })
    }
    const reason = sourceRejectReason(apDraft)
    const displayStatus = generated
      ? (existed?.paymentDraftStatus === 'paymentReady' ? 'paymentPending' : 'paymentDraftGenerated')
      : apDraft.apStatus
    return {
      ...apDraft,
      apStatus: displayStatus,
      totalPayableAmount,
      paidAmount,
      unpaidAmount,
      paymentDraftGenerated: generated,
      paymentDraftGeneratedText: generated ? (existed?.paymentDraftStatus === 'paymentReady' ? '等待付款' : '已生成') : '未生成',
      targetPaymentDraftId: apDraft.targetPaymentDraftId || existed?.id || '',
      targetPaymentDraftNo: apDraft.targetPaymentDraftNo || existed?.paymentDraftNo || '',
      targetPaymentDraftStatus: existed?.paymentDraftStatus || '',
      canCreatePaymentDraft: !reason,
      sourceRejectReason: reason,
    }
  })
}

function buildLinesFromApDraft(apDraft = {}) {
  return (apDraft.lines || []).map((line, index) => {
    const payableAmount = roundAmount(line.payableAmount ?? line.invoiceAmount)
    const paidAmount = roundAmount(line.paidAmount ?? 0)
    const unpaidAmount = roundAmount(Math.max(payableAmount - paidAmount, 0))
    return normalizeLine({
      ...line,
      lineNo: index + 1,
      payableAmount,
      paidAmount,
      unpaidAmount,
      applyPayAmount: unpaidAmount,
      sourceApDraftLineId: line.id,
      sourceInventoryTransactionId: line.sourceInventoryTransactionId || '',
      sourceInventoryTransactionNo: line.sourceInventoryTransactionNo || '',
      sourcePurchaseOrderNo: line.sourcePurchaseOrderNo || apDraft.sourcePurchaseOrderNo,
      sourceReceiveNo: line.sourceReceiveNo || apDraft.sourceReceiveNo,
      sourceInspectionNo: line.sourceInspectionNo || apDraft.sourceInspectionNo,
      rootRequestNo: line.rootRequestNo || apDraft.rootRequestNo,
    }, index)
  })
}

export function createPaymentDraftFromApDraft(apDraftId) {
  const apDraft = getAccountPayableDraftById(apDraftId)
  const reason = sourceRejectReason(apDraft)
  if (reason) {
    writePaymentDraftLog('防重复生成拦截', {
      sourceNo: apDraft?.apDraftNo || apDraftId,
      targetId: apDraftId,
      result: reason,
    })
    return { success: false, error: reason }
  }
  const totalPayableAmount = roundAmount(apDraft.totalPayableAmount)
  const paidAmount = roundAmount(apDraft.paidAmount ?? 0)
  const unpaidAmount = roundAmount(apDraft.unpaidAmount ?? totalPayableAmount - paidAmount)
  const draft = supplierPaymentDraft({
    sourceApDraftId: apDraft.id,
    sourceApDraftNo: apDraft.apDraftNo,
    sourceInvoicePrepareNo: apDraft.sourceInvoicePrepareNo,
    sourcePayableCheckNo: apDraft.sourcePayableCheckNo,
    sourcePayablePrepareNo: apDraft.sourcePayablePrepareNo,
    sourceInventoryTransactionIds: apDraft.sourceInventoryTransactionIds || [],
    sourceInventoryTransactionNos: apDraft.sourceInventoryTransactionNos || (apDraft.lines || []).map((line) => line.sourceInventoryTransactionNo).filter(Boolean),
    supplierId: apDraft.supplierId,
    supplierName: apDraft.supplierName,
    sourcePurchaseOrderNo: apDraft.sourcePurchaseOrderNo,
    sourceReceiveNo: apDraft.sourceReceiveNo,
    sourceInspectionNo: apDraft.sourceInspectionNo,
    rootRequestNo: apDraft.rootRequestNo,
    expectedPayDate: apDraft.expectedPayDate || apDraft.dueDate || '',
    dueDate: apDraft.dueDate || apDraft.expectedPayDate || '',
    totalPayableAmount,
    paidAmount,
    unpaidAmount,
    applyPayAmount: unpaidAmount,
    paymentRemark: '由应付账款草稿生成，仅形成付款申请预备数据，不执行真实付款，不生成银行付款或财务凭证。',
    lines: buildLinesFromApDraft(apDraft),
  })
  state.supplierPaymentDrafts.unshift(draft)
  persist()
  const writeBack = markApDraftPaymentDraftGenerated(apDraft.id, draft)
  writePaymentDraftLog('从应付账款草稿生成供应商付款草稿', {
    sourceNo: apDraft.apDraftNo,
    targetId: draft.id,
    targetNo: draft.paymentDraftNo,
    result: draft.applyPayAmount,
  })
  return { success: true, paymentDraftId: draft.id, paymentDraftNo: draft.paymentDraftNo, supplierPaymentDraft: clone(draft), writeBackSuccess: Boolean(writeBack?.success) }
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
  writePaymentDraftLog(label, { targetType: 'batch', targetId: label, result: `成功 ${result.successCount} 条，已回写 ${writeBackCount} 条，失败 ${result.failedCount} 条；${result.failedReason.join('；')}` })
  if (result.failedCount) writePaymentDraftLog('批量失败原因', { targetType: 'batch', targetId: label, result: result.failedReason.join('；') })
  return result
}

export function batchCreatePaymentDraftsFromApDrafts(ids = []) {
  return batchResult(ids, createPaymentDraftFromApDraft, '批量生成供应商付款草稿', (id) => getAccountPayableDraftById(id)?.apDraftNo || id)
}

export function updatePaymentDraft(id, patch = {}) {
  const current = byId(state.supplierPaymentDrafts, id)
  if (!current || !['draft', 'submitted'].includes(current.paymentDraftStatus)) return { success: false, error: '当前付款草稿不可修改。' }
  const nextApplyPayAmount = roundAmount(patch.applyPayAmount ?? current.applyPayAmount)
  if (nextApplyPayAmount < 0) return { success: false, error: '申请付款金额不能小于 0。' }
  if (nextApplyPayAmount > roundAmount(current.unpaidAmount)) return { success: false, error: '申请付款金额不能大于未付款金额。' }
  Object.assign(current, supplierPaymentDraft({ ...current, ...patch, id: current.id, updatedAt: nowText() }))
  persist()
  writePaymentDraftLog('更新供应商付款草稿', { targetId: current.id, targetNo: current.paymentDraftNo })
  return { success: true, supplierPaymentDraft: clone(current) }
}

function markStatus(id, status, action, patch = {}) {
  const current = byId(state.supplierPaymentDrafts, id)
  if (!current) return { success: false, error: '未找到供应商付款草稿。' }
  if (['cancelled', 'closed'].includes(current.paymentDraftStatus)) return { success: false, error: '已取消或已关闭的付款草稿不能继续流转。' }
  Object.assign(current, patch, { paymentDraftStatus: status, updatedAt: nowText() })
  if (status === 'submitted') current.approvalStatus = 'submitted'
  if (status === 'approved') current.approvalStatus = 'approved'
  if (status === 'paymentReady') {
    current.paymentReady = true
    current.approvalStatus = 'approved'
    current.paymentStatus = 'unpaid'
  }
  persist()
  writePaymentDraftLog(action, { targetId: current.id, targetNo: current.paymentDraftNo, sourceNo: current.sourceApDraftNo })
  return { success: true, supplierPaymentDraft: clone(current) }
}

export function submitPaymentDraft(id) {
  const current = byId(state.supplierPaymentDrafts, id)
  if (current && current.paymentDraftStatus !== 'draft') return { success: false, error: '只有草稿状态可提交付款申请。' }
  return markStatus(id, 'submitted', '提交付款申请')
}

export function approvePaymentDraft(id) {
  const current = byId(state.supplierPaymentDrafts, id)
  if (current && current.paymentDraftStatus !== 'submitted') return { success: false, error: '只有已提交状态可审批付款申请。' }
  return markStatus(id, 'approved', '审批付款申请')
}

export function markPaymentReady(id) {
  const current = byId(state.supplierPaymentDrafts, id)
  if (current && current.paymentDraftStatus !== 'approved') return { success: false, error: '只有已审批状态可标记可付款。' }
  return markStatus(id, 'paymentReady', '标记可付款')
}

export function cancelPaymentDraft(id) {
  const current = byId(state.supplierPaymentDrafts, id)
  if (current && !['draft', 'submitted'].includes(current.paymentDraftStatus)) return { success: false, error: '只有草稿或已提交状态可取消付款草稿。' }
  return markStatus(id, 'cancelled', '取消付款草稿', { approvalStatus: 'cancelled' })
}

export function batchSubmitPaymentDrafts(ids = []) {
  return batchResult(ids, submitPaymentDraft, '批量提交付款申请', (id) => byId(state.supplierPaymentDrafts, id)?.paymentDraftNo || id)
}

export function batchApprovePaymentDrafts(ids = []) {
  return batchResult(ids, approvePaymentDraft, '批量审批付款申请', (id) => byId(state.supplierPaymentDrafts, id)?.paymentDraftNo || id)
}

export function batchMarkPaymentReady(ids = []) {
  return batchResult(ids, markPaymentReady, '批量标记可付款', (id) => byId(state.supplierPaymentDrafts, id)?.paymentDraftNo || id)
}

export function batchCancelPaymentDrafts(ids = []) {
  return batchResult(ids, cancelPaymentDraft, '批量取消付款草稿', (id) => byId(state.supplierPaymentDrafts, id)?.paymentDraftNo || id)
}
