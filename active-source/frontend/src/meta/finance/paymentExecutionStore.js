import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  getPaymentExecutionRiskReviewById,
  listPaymentExecutionRiskReviews,
  markPaymentRiskReviewPaymentExecutionGenerated,
} from './paymentExecutionRiskReviewStore.js'
import { markPaymentOrderDraftPaymentExecutionGenerated } from './paymentOrderDraftStore.js'

const STORAGE_KEY = 'payment-execution-draft-state-v1'

const ACTIVE_STATUSES = [
  'draft',
  'confirmed',
  'waitingOfflinePayment',
  'offlinePaymentRecorded',
  'recordReviewPending',
]

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

function toSafeAmount(value) {
  const normalized = Number(String(value ?? 0).replace(/,/g, '').trim())
  if (!Number.isFinite(normalized)) return 0
  return Math.round(normalized * 100) / 100
}

function hasText(value) {
  return String(value || '').trim().length > 0
}

function normalizeLine(line = {}, index = 0) {
  const executionAmount = toSafeAmount(line.executionAmount ?? line.confirmedPayAmount ?? line.payAmount)
  return {
    id: line.id || createId('pel'),
    lineNo: line.lineNo || index + 1,
    itemName: line.itemName || line.materialName || line.sourcePaymentOrderDraftNo || '付款执行草稿明细',
    sourceNo: line.sourceNo || line.sourcePaymentOrderDraftNo || '',
    executionAmount,
    remark: line.remark || '',
  }
}

function normalizeExecution(item = {}) {
  const lines = Array.isArray(item.lines) && item.lines.length
    ? item.lines.map(normalizeLine)
    : [normalizeLine({
      sourcePaymentOrderDraftNo: item.sourcePaymentOrderDraftNo,
      executionAmount: item.executionAmount ?? item.confirmedPayAmount,
    })]

  const executionAmount = toSafeAmount(item.executionAmount ?? lines.reduce((sum, line) => sum + toSafeAmount(line.executionAmount), 0))
  const unpaidAmount = toSafeAmount(item.unpaidAmount ?? executionAmount)

  return {
    id: item.id || createId('pex'),
    paymentExecutionNo: item.paymentExecutionNo || createNo('PEX'),
    sourceRiskReviewId: item.sourceRiskReviewId || '',
    sourceRiskReviewNo: item.sourceRiskReviewNo || '',
    sourcePaymentOrderDraftId: item.sourcePaymentOrderDraftId || '',
    sourcePaymentOrderDraftNo: item.sourcePaymentOrderDraftNo || '',
    sourcePaymentPrepareNo: item.sourcePaymentPrepareNo || '',
    sourcePaymentDraftNo: item.sourcePaymentDraftNo || '',
    sourceApDraftNo: item.sourceApDraftNo || '',
    sourceInvoicePrepareNo: item.sourceInvoicePrepareNo || '',
    sourcePayableCheckNo: item.sourcePayableCheckNo || '',
    sourcePayablePrepareNo: item.sourcePayablePrepareNo || '',
    sourceInventoryTransactionNos: Array.isArray(item.sourceInventoryTransactionNos) ? item.sourceInventoryTransactionNos : [],
    sourceInspectionNo: item.sourceInspectionNo || '',
    sourceReceiveNo: item.sourceReceiveNo || '',
    sourcePurchaseOrderNo: item.sourcePurchaseOrderNo || '',
    rootRequestNo: item.rootRequestNo || '',
    supplierId: item.supplierId || '',
    supplierName: item.supplierName || '',
    paymentMethod: item.paymentMethod || '线下转账',
    paymentAccount: item.paymentAccount || '',
    paymentAccountName: item.paymentAccountName || '',
    paymentBankName: item.paymentBankName || '',
    supplierBankName: item.supplierBankName || '',
    supplierBankAccount: item.supplierBankAccount || '',
    supplierBankAccountName: item.supplierBankAccountName || '',
    executionAmount,
    unpaidAmount,
    expectedPayDate: item.expectedPayDate || today(),
    actualPayDate: item.actualPayDate || '',
    offlinePaymentRecordNo: item.offlinePaymentRecordNo || '',
    offlinePaymentRemark: item.offlinePaymentRemark || '',
    offlinePaymentRecorded: Boolean(item.offlinePaymentRecorded),
    submittedForReview: Boolean(item.submittedForReview),
    paymentRecordReviewGenerated: Boolean(item.paymentRecordReviewGenerated),
    targetPaymentRecordReviewId: item.targetPaymentRecordReviewId || '',
    targetPaymentRecordReviewNo: item.targetPaymentRecordReviewNo || '',
    targetModule: item.targetModule || '',
    paymentRecordReviewStatus: item.paymentRecordReviewStatus || '',
    paymentRecordReviewGeneratedAt: item.paymentRecordReviewGeneratedAt || '',
    paymentExecutionStatus: item.paymentExecutionStatus || 'draft',
    realPaymentStatus: item.realPaymentStatus || 'notPaid',
    voucherStatus: item.voucherStatus || 'notGenerated',
    ledgerStatus: item.ledgerStatus || 'notPosted',
    paymentRiskReviewStatus: item.paymentRiskReviewStatus || '',
    riskLevel: item.riskLevel || '',
    lines,
    createdAt: item.createdAt || nowText(),
    updatedAt: item.updatedAt || nowText(),
    confirmedAt: item.confirmedAt || '',
    waitingOfflinePaymentAt: item.waitingOfflinePaymentAt || '',
    offlineRecordedAt: item.offlineRecordedAt || '',
    recordReviewSubmittedAt: item.recordReviewSubmittedAt || '',
    cancelledAt: item.cancelledAt || '',
  }
}

function defaultState() {
  return {
    paymentExecutions: [],
  }
}

function normalizeState(raw = {}) {
  return {
    paymentExecutions: (raw.paymentExecutions || []).map(normalizeExecution),
  }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[PAYMENT EXECUTION STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function byId(id) {
  return state.paymentExecutions.find((item) => String(item.id) === String(id)) || null
}

function activeByRiskReviewId(riskReviewId) {
  return state.paymentExecutions.find((item) => (
    String(item.sourceRiskReviewId) === String(riskReviewId)
    && ACTIVE_STATUSES.includes(item.paymentExecutionStatus)
  )) || null
}

function activeByPaymentOrderDraftId(paymentOrderDraftId) {
  return state.paymentExecutions.find((item) => (
    String(item.sourcePaymentOrderDraftId) === String(paymentOrderDraftId)
    && ACTIVE_STATUSES.includes(item.paymentExecutionStatus)
  )) || null
}

function writePaymentExecutionLog(action, payload = {}) {
  addOperationLog({
    module: '付款执行草稿',
    action,
    targetType: payload.targetType || 'paymentExecutionDraft',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源单据：${payload.sourceNo || '-'}`,
      `目标单据：${payload.targetNo || '-'}`,
      `结果：${payload.result || '成功'}`,
      '边界：本动作不执行真实付款、不连接银行、不生成银行流水、不生成财务凭证、不写总账。',
    ].join('；'),
  })
}

function sourceAmount(review = {}) {
  const payAmount = toSafeAmount(review.checkPayAmount ?? review.confirmedPayAmount)
  const unpaidAmount = toSafeAmount(review.checkUnpaidAmount ?? review.unpaidAmount ?? payAmount)
  return {
    payAmount,
    unpaidAmount,
    payAmountCents: Math.round(payAmount * 100),
    unpaidAmountCents: Math.round(unpaidAmount * 100),
  }
}

function hasMockBankInfo(review = {}) {
  return Boolean(
    review.bankInfoMocked
    || review.paymentBankInfoMocked
    || review.supplierBankInfoMocked
    || String(review.bankInfoMockRemark || '').includes('模拟')
  )
}

function buildExecutionFromReview(review = {}) {
  const amounts = sourceAmount(review)
  return normalizeExecution({
    sourceRiskReviewId: review.id,
    sourceRiskReviewNo: review.riskReviewNo,
    sourcePaymentOrderDraftId: review.sourcePaymentOrderDraftId,
    sourcePaymentOrderDraftNo: review.sourcePaymentOrderDraftNo,
    sourcePaymentPrepareNo: review.sourcePaymentPrepareNo,
    sourcePaymentDraftNo: review.sourcePaymentDraftNo,
    sourceApDraftNo: review.sourceApDraftNo,
    sourceInvoicePrepareNo: review.sourceInvoicePrepareNo,
    sourcePayableCheckNo: review.sourcePayableCheckNo,
    sourcePayablePrepareNo: review.sourcePayablePrepareNo,
    sourceInventoryTransactionNos: review.sourceInventoryTransactionNos || [],
    sourceInspectionNo: review.sourceInspectionNo,
    sourceReceiveNo: review.sourceReceiveNo,
    sourcePurchaseOrderNo: review.sourcePurchaseOrderNo,
    rootRequestNo: review.rootRequestNo,
    supplierId: review.supplierId,
    supplierName: review.supplierName,
    paymentAccount: review.paymentAccount,
    paymentAccountName: review.paymentAccountName,
    paymentBankName: review.paymentBankName,
    supplierBankName: review.supplierBankName,
    supplierBankAccount: review.supplierBankAccount,
    supplierBankAccountName: review.supplierBankAccountName,
    executionAmount: amounts.payAmount,
    unpaidAmount: amounts.unpaidAmount,
    paymentRiskReviewStatus: review.riskReviewStatus,
    riskLevel: review.riskLevel,
  })
}

function syncPaymentExecutionSources(execution = {}) {
  if (!execution?.id) return
  if (execution.sourceRiskReviewId) {
    markPaymentRiskReviewPaymentExecutionGenerated(execution.sourceRiskReviewId, execution)
  }
  if (execution.sourcePaymentOrderDraftId) {
    markPaymentOrderDraftPaymentExecutionGenerated(execution.sourcePaymentOrderDraftId, execution)
  }
}

export function getPaymentExecutionState() {
  return clone(state)
}

export function listPaymentExecutions() {
  return clone(state.paymentExecutions)
}

export function getPaymentExecutionById(id) {
  const item = byId(id)
  return item ? clone(item) : null
}

export function isPaymentExecutionGenerated(riskReviewId) {
  const existing = activeByRiskReviewId(riskReviewId)
  return existing ? clone(existing) : null
}

export function getPaymentExecutionByPaymentOrderDraftId(paymentOrderDraftId) {
  const existing = activeByPaymentOrderDraftId(paymentOrderDraftId)
  return existing ? clone(existing) : null
}

export function markPaymentExecutionPaymentRecordReviewGenerated(id, review = {}) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款执行草稿。' }
  Object.assign(current, {
    paymentRecordReviewGenerated: true,
    targetPaymentRecordReviewId: review.id || review.targetPaymentRecordReviewId || current.targetPaymentRecordReviewId || '',
    targetPaymentRecordReviewNo: review.paymentRecordReviewNo || review.targetPaymentRecordReviewNo || current.targetPaymentRecordReviewNo || '',
    targetModule: 'paymentRecordReview',
    paymentRecordReviewStatus: review.reviewStatus || review.paymentRecordReviewStatus || current.paymentRecordReviewStatus || 'pending',
    paymentRecordReviewGeneratedAt: current.paymentRecordReviewGeneratedAt || nowText(),
    updatedAt: nowText(),
  })
  persist()
  syncPaymentExecutionSources(current)
  writePaymentExecutionLog('回写付款记录复核任务', {
    sourceNo: current.paymentExecutionNo,
    targetId: current.targetPaymentRecordReviewId,
    targetNo: current.targetPaymentRecordReviewNo,
    result: '已生成付款记录复核任务；仍未执行真实付款。',
  })
  return { success: true, execution: clone(current) }
}

export function markPaymentExecutionPaymentRecordReviewStatus(id, review = {}) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款执行草稿。' }
  Object.assign(current, {
    paymentRecordReviewGenerated: current.paymentRecordReviewGenerated || Boolean(current.targetPaymentRecordReviewId),
    targetPaymentRecordReviewId: current.targetPaymentRecordReviewId,
    targetPaymentRecordReviewNo: current.targetPaymentRecordReviewNo,
    targetModule: current.targetModule || 'paymentRecordReview',
    paymentRecordReviewStatus: review.reviewStatus || current.paymentRecordReviewStatus,
    realPaymentStatus: review.realPaymentStatus || current.realPaymentStatus,
    voucherStatus: review.voucherStatus || current.voucherStatus || 'notGenerated',
    ledgerStatus: review.ledgerStatus || current.ledgerStatus || 'notPosted',
    updatedAt: nowText(),
  })
  persist()
  syncPaymentExecutionSources(current)
  writePaymentExecutionLog('同步付款记录复核状态', {
    sourceNo: current.paymentExecutionNo,
    targetId: current.targetPaymentRecordReviewId,
    targetNo: current.targetPaymentRecordReviewNo,
    result: `付款记录复核状态：${review.reviewStatus || current.paymentRecordReviewStatus || '-'}`,
  })
  return { success: true, execution: clone(current) }
}

export function getPaymentExecutionSourcesFromRiskReviews() {
  return listPaymentExecutionRiskReviews().map((review) => {
    const existing = activeByRiskReviewId(review.id)
    const amounts = sourceAmount(review)
    const passed = review.riskReviewStatus === 'passed' && review.riskLevel === 'low'
    const amountOk = amounts.payAmountCents > 0 && amounts.payAmountCents <= amounts.unpaidAmountCents
    const mockBank = hasMockBankInfo(review)
    let disabledReason = ''
    if (!passed) disabledReason = '风险评审尚未通过。'
    else if (mockBank) disabledReason = '仍存在模拟银行信息，不能生成付款执行草稿。'
    else if (!amountOk) disabledReason = '付款金额必须大于 0，且不能超过未付款金额。'
    else if (existing) disabledReason = '已存在未关闭的付款执行草稿。'

    return {
      ...review,
      checkPayAmount: amounts.payAmount,
      checkUnpaidAmount: amounts.unpaidAmount,
      paymentExecutionGenerated: Boolean(existing),
      paymentExecutionId: existing?.id || '',
      paymentExecutionNo: existing?.paymentExecutionNo || '',
      canGeneratePaymentExecution: !disabledReason,
      disabledReason,
    }
  })
}

export function createPaymentExecutionFromRiskReview(riskReviewId) {
  const review = getPaymentExecutionRiskReviewById(riskReviewId)
  if (!review) return { success: false, error: '未找到真实付款风险评审记录。' }

  const existing = activeByRiskReviewId(review.id)
  if (existing) {
    syncPaymentExecutionSources(existing)
    writePaymentExecutionLog('防重复生成付款执行草稿', {
      sourceNo: review.riskReviewNo,
      targetId: existing.id,
      targetNo: existing.paymentExecutionNo,
      result: '已存在未关闭的付款执行草稿，无需重复生成。',
    })
    return {
      success: true,
      alreadyDone: true,
      execution: clone(existing),
      message: '该风险评审已生成未关闭的付款执行草稿，无需重复生成。',
    }
  }

  const amounts = sourceAmount(review)
  if (review.riskReviewStatus !== 'passed' || review.riskLevel !== 'low') {
    return { success: false, error: '只有评审通过且低风险的记录才能生成付款执行草稿。' }
  }
  if (hasMockBankInfo(review)) {
    writePaymentExecutionLog('模拟银行信息阻断付款执行草稿生成', {
      sourceNo: review.riskReviewNo,
      result: '存在模拟银行信息。',
    })
    return { success: false, error: '存在模拟银行信息，不能生成付款执行草稿。' }
  }
  if (amounts.payAmountCents <= 0) return { success: false, error: '付款执行金额必须大于 0。' }
  if (amounts.payAmountCents > amounts.unpaidAmountCents) return { success: false, error: '付款执行金额不能超过未付款金额。' }

  const execution = buildExecutionFromReview(review)
  state.paymentExecutions.unshift(execution)
  persist()
  syncPaymentExecutionSources(execution)
  writePaymentExecutionLog('生成付款执行草稿', {
    sourceNo: review.riskReviewNo,
    targetId: execution.id,
    targetNo: execution.paymentExecutionNo,
    result: '已生成付款执行草稿；尚未执行真实付款。',
  })
  return { success: true, execution: clone(execution) }
}

function transitionPaymentExecution(id, config = {}) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款执行草稿。' }
  if (current.paymentExecutionStatus === config.targetStatus) {
    return {
      success: true,
      alreadyDone: true,
      execution: clone(current),
      message: config.alreadyDoneMessage || '当前状态已达成，无需重复操作。',
    }
  }
  if (!config.from.includes(current.paymentExecutionStatus)) {
    return { success: false, error: config.invalidMessage || '当前状态不允许执行该操作。' }
  }
  const patch = typeof config.patch === 'function' ? config.patch(current) : (config.patch || {})
  Object.assign(current, patch, {
    paymentExecutionStatus: config.targetStatus,
    updatedAt: nowText(),
  })
  persist()
  syncPaymentExecutionSources(current)
  writePaymentExecutionLog(config.action, {
    sourceNo: current.sourceRiskReviewNo,
    targetId: current.id,
    targetNo: current.paymentExecutionNo,
    result: config.logResult || getPaymentExecutionStatusLabel(config.targetStatus),
  })
  return { success: true, execution: clone(current) }
}

export function confirmPaymentExecution(id) {
  return transitionPaymentExecution(id, {
    from: ['draft'],
    targetStatus: 'confirmed',
    action: '确认付款执行',
    logResult: '已完成内部付款执行确认；不代表已经付款。',
    alreadyDoneMessage: '该付款执行草稿已确认，无需重复确认。',
    invalidMessage: '只有草稿状态可以确认付款执行。',
    patch: () => ({ confirmedAt: nowText() }),
  })
}

export function markWaitingOfflinePayment(id) {
  return transitionPaymentExecution(id, {
    from: ['confirmed'],
    targetStatus: 'waitingOfflinePayment',
    action: '标记等待线下付款',
    logResult: '已标记等待线下付款；尚未登记线下结果。',
    alreadyDoneMessage: '该付款执行草稿已处于等待线下付款状态。',
    invalidMessage: '只有已确认的付款执行草稿可以标记等待线下付款。',
    patch: () => ({ waitingOfflinePaymentAt: nowText(), realPaymentStatus: 'notPaid' }),
  })
}

export function recordOfflinePaymentDraft(id, payload = {}) {
  return transitionPaymentExecution(id, {
    from: ['waitingOfflinePayment'],
    targetStatus: 'offlinePaymentRecorded',
    action: '登记线下付款结果草稿',
    logResult: '已登记线下付款结果草稿；不是银行回单，不代表真实付款完成。',
    alreadyDoneMessage: '该付款执行草稿已登记线下付款结果草稿。',
    invalidMessage: '只有等待线下付款状态可以登记线下付款结果草稿。',
    patch: () => ({
      offlinePaymentRecorded: true,
      offlinePaymentRecordNo: payload.offlinePaymentRecordNo || createNo('OPR'),
      actualPayDate: payload.actualPayDate || today(),
      offlinePaymentRemark: payload.offlinePaymentRemark || '线下付款结果草稿，待后续复核。',
      offlineRecordedAt: nowText(),
      realPaymentStatus: 'offlineRecorded',
    }),
  })
}

export function submitPaymentRecordReview(id) {
  return transitionPaymentExecution(id, {
    from: ['offlinePaymentRecorded'],
    targetStatus: 'recordReviewPending',
    action: '提交付款记录复核',
    logResult: '已提交付款记录复核；本轮不做复核通过、不生成凭证。',
    alreadyDoneMessage: '该付款执行草稿已提交付款记录复核。',
    invalidMessage: '只有已登记线下付款结果草稿的记录可以提交复核。',
    patch: () => ({ submittedForReview: true, recordReviewSubmittedAt: nowText() }),
  })
}

export function cancelPaymentExecution(id) {
  return transitionPaymentExecution(id, {
    from: ['draft', 'confirmed', 'waitingOfflinePayment', 'offlinePaymentRecorded'],
    targetStatus: 'cancelled',
    action: '取消付款执行草稿',
    logResult: '已取消付款执行草稿；未执行真实付款。',
    alreadyDoneMessage: '该付款执行草稿已取消。',
    invalidMessage: '当前状态不能取消付款执行草稿。',
    patch: () => ({ cancelledAt: nowText() }),
  })
}

function batchResult(ids = [], handler, label, noGetter = (id) => id) {
  const result = {
    operationName: label,
    total: ids.length,
    successCount: 0,
    alreadyDoneCount: 0,
    failedCount: 0,
    successItems: [],
    alreadyDoneItems: [],
    failedReason: [],
    nextSuggestion: '',
  }
  ids.forEach((id) => {
    const no = noGetter(id)
    const outcome = handler(id)
    if (!outcome?.success) {
      result.failedCount += 1
      result.failedReason.push(`${no}：${outcome?.error || '当前记录不满足批量操作条件。'}`)
      return
    }
    const execution = outcome.execution || {}
    if (outcome.alreadyDone) {
      result.alreadyDoneCount += 1
      result.alreadyDoneItems.push({ id, no, status: execution.paymentExecutionStatus })
    } else {
      result.successCount += 1
      result.successItems.push({ id, no, status: execution.paymentExecutionStatus })
    }
  })
  result.nextSuggestion = result.failedCount
    ? '请按失败原因处理后再重试；本批量动作不会执行真实付款。'
    : '本批量动作已完成或已达成；后续仍需按流程复核，不会自动付款。'
  writePaymentExecutionLog(label, {
    targetType: 'batchPaymentExecution',
    targetId: label,
    result: `成功 ${result.successCount} 条，已达成 ${result.alreadyDoneCount} 条，失败 ${result.failedCount} 条；${result.failedReason.join('；')}`,
  })
  return result
}

export function batchCreatePaymentExecutions(riskReviewIds = []) {
  return batchResult(riskReviewIds, createPaymentExecutionFromRiskReview, '批量生成付款执行草稿', (id) => getPaymentExecutionRiskReviewById(id)?.riskReviewNo || id)
}

export function batchConfirmPaymentExecutions(ids = []) {
  return batchResult(ids, confirmPaymentExecution, '批量确认付款执行', (id) => byId(id)?.paymentExecutionNo || id)
}

export function batchMarkWaitingOfflinePayment(ids = []) {
  return batchResult(ids, markWaitingOfflinePayment, '批量标记等待线下付款', (id) => byId(id)?.paymentExecutionNo || id)
}

export function batchRecordOfflinePaymentDraft(ids = []) {
  return batchResult(ids, recordOfflinePaymentDraft, '批量登记线下付款结果草稿', (id) => byId(id)?.paymentExecutionNo || id)
}

export function batchSubmitPaymentRecordReview(ids = []) {
  return batchResult(ids, submitPaymentRecordReview, '批量提交付款记录复核', (id) => byId(id)?.paymentExecutionNo || id)
}

export function batchCancelPaymentExecutions(ids = []) {
  return batchResult(ids, cancelPaymentExecution, '批量取消付款执行草稿', (id) => byId(id)?.paymentExecutionNo || id)
}

export function getPaymentExecutionStatusLabel(status) {
  return {
    draft: '草稿',
    confirmed: '已确认付款执行',
    waitingOfflinePayment: '等待线下付款',
    offlinePaymentRecorded: '已登记线下付款结果草稿',
    recordReviewPending: '付款记录待复核',
    cancelled: '已取消',
    closed: '已关闭',
  }[status] || status || '-'
}

export function getPaymentExecutionStatusType(status) {
  return {
    draft: 'info',
    confirmed: 'primary',
    waitingOfflinePayment: 'warning',
    offlinePaymentRecorded: 'success',
    recordReviewPending: 'warning',
    cancelled: 'info',
    closed: 'info',
  }[status] || 'info'
}

export function getRealPaymentStatusLabel(status) {
  return {
    notPaid: '未执行真实付款',
    offlineRecorded: '已登记线下付款结果草稿',
    paymentRecordReviewed: '付款记录已复核',
  }[status] || status || '-'
}

export function getVoucherStatusLabel(status) {
  return {
    notGenerated: '未生成凭证',
  }[status] || status || '-'
}

export function getLedgerStatusLabel(status) {
  return {
    notPosted: '未写总账',
  }[status] || status || '-'
}
