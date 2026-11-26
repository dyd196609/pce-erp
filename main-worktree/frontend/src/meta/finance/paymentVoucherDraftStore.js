import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  getPaymentRecordReviewById,
  listPaymentRecordReviews,
  markPaymentRecordReviewPaymentVoucherDraftGenerated,
  markPaymentRecordReviewPaymentVoucherDraftStatus,
} from './paymentRecordReviewStore.js'

const STORAGE_KEY = 'payment-voucher-draft-state-v1'
const ACTIVE_STATUSES = ['draft', 'readyForReview', 'reviewed']

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function nowText() {
  return new Date().toISOString()
}

function today() {
  return new Date().toISOString().slice(0, 10)
}

function currentPeriod() {
  return today().slice(0, 7)
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

function defaultState() {
  return { paymentVoucherDrafts: [] }
}

function normalizeLine(line = {}, index = 0, source = {}) {
  const amount = toSafeAmount(line.amount ?? source.totalVoucherAmount)
  return {
    id: line.id || createId('pvdl'),
    lineNo: line.lineNo || index + 1,
    direction: line.direction || 'debit',
    accountCode: line.accountCode || '',
    accountName: line.accountName || '',
    amount,
    cashFlowItem: line.cashFlowItem || '',
    sourcePaymentRecordReviewLineId: line.sourcePaymentRecordReviewLineId || '',
    sourcePurchaseOrderNo: line.sourcePurchaseOrderNo || source.sourcePurchaseOrderNo || '',
    sourceReceiveNo: line.sourceReceiveNo || source.sourceReceiveNo || '',
    sourceInspectionNo: line.sourceInspectionNo || source.sourceInspectionNo || '',
    sourceInventoryTransactionNo: line.sourceInventoryTransactionNo || (source.sourceInventoryTransactionNos || [])[0] || '',
    rootRequestNo: line.rootRequestNo || source.rootRequestNo || '',
    remark: line.remark || '',
  }
}

function normalizeDraft(item = {}) {
  const lines = Array.isArray(item.lines) ? item.lines.map((line, index) => normalizeLine(line, index, item)) : []
  const debitAmount = toSafeAmount(item.debitAmount ?? lines.filter((line) => line.direction === 'debit').reduce((sum, line) => sum + toSafeAmount(line.amount), 0))
  const creditAmount = toSafeAmount(item.creditAmount ?? lines.filter((line) => line.direction === 'credit').reduce((sum, line) => sum + toSafeAmount(line.amount), 0))
  return {
    id: item.id || createId('pvd'),
    voucherDraftNo: item.voucherDraftNo || createNo('PVD'),
    sourcePaymentRecordReviewId: item.sourcePaymentRecordReviewId || '',
    sourcePaymentRecordReviewNo: item.sourcePaymentRecordReviewNo || '',
    sourcePaymentExecutionNo: item.sourcePaymentExecutionNo || '',
    sourceRiskReviewNo: item.sourceRiskReviewNo || '',
    sourcePaymentOrderDraftNo: item.sourcePaymentOrderDraftNo || '',
    sourcePaymentPrepareNo: item.sourcePaymentPrepareNo || '',
    sourcePaymentDraftNo: item.sourcePaymentDraftNo || '',
    sourceApDraftNo: item.sourceApDraftNo || '',
    sourceInvoicePrepareNo: item.sourceInvoicePrepareNo || '',
    sourcePayableCheckNo: item.sourcePayableCheckNo || '',
    sourcePayablePrepareNo: item.sourcePayablePrepareNo || '',
    supplierId: item.supplierId || '',
    supplierName: item.supplierName || '',
    sourcePurchaseOrderNo: item.sourcePurchaseOrderNo || '',
    sourceReceiveNo: item.sourceReceiveNo || '',
    sourceInspectionNo: item.sourceInspectionNo || '',
    sourceInventoryTransactionNos: Array.isArray(item.sourceInventoryTransactionNos) ? item.sourceInventoryTransactionNos : [],
    rootRequestNo: item.rootRequestNo || '',
    voucherDate: item.voucherDate || today(),
    accountingPeriod: item.accountingPeriod || currentPeriod(),
    totalVoucherAmount: toSafeAmount(item.totalVoucherAmount ?? debitAmount),
    debitAmount,
    creditAmount,
    differenceAmount: toSafeAmount(item.differenceAmount ?? debitAmount - creditAmount),
    voucherStatus: item.voucherStatus || 'draft',
    reviewStatus: item.reviewStatus || 'notSubmitted',
    paymentVoucherReviewGenerated: Boolean(item.paymentVoucherReviewGenerated),
    targetPaymentVoucherReviewId: item.targetPaymentVoucherReviewId || '',
    targetPaymentVoucherReviewNo: item.targetPaymentVoucherReviewNo || '',
    targetModule: item.targetModule || '',
    voucherReviewStatus: item.voucherReviewStatus || '',
    voucherReviewResult: item.voucherReviewResult || '',
    voucherReviewerId: item.voucherReviewerId || '',
    voucherReviewerName: item.voucherReviewerName || '',
    voucherReviewerRole: item.voucherReviewerRole || '',
    voucherReviewerSource: item.voucherReviewerSource || '',
    voucherReviewedAt: item.voucherReviewedAt || '',
    paymentVoucherReviewGeneratedAt: item.paymentVoucherReviewGeneratedAt || '',
    ledgerStatus: item.ledgerStatus || 'notPosted',
    riskStatus: item.riskStatus || 'pending',
    riskLevel: item.riskLevel || 'pending',
    riskItems: Array.isArray(item.riskItems) ? item.riskItems : [],
    createdBy: item.createdBy || '当前制单人',
    reviewedBy: item.reviewedBy || '',
    cancelledBy: item.cancelledBy || '',
    createdAt: item.createdAt || nowText(),
    submittedAt: item.submittedAt || '',
    submittedBy: item.submittedBy || '',
    reviewedAt: item.reviewedAt || '',
    cancelledAt: item.cancelledAt || '',
    updatedAt: item.updatedAt || nowText(),
    lines,
    operationLogs: Array.isArray(item.operationLogs) ? item.operationLogs : [],
  }
}

function normalizeState(raw = {}) {
  return {
    paymentVoucherDrafts: (raw.paymentVoucherDrafts || []).map(normalizeDraft),
  }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[PAYMENT VOUCHER DRAFT STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function byId(id) {
  return state.paymentVoucherDrafts.find((item) => String(item.id) === String(id)) || null
}

function activeByRecordReviewId(recordReviewId) {
  return state.paymentVoucherDrafts.find((item) => (
    String(item.sourcePaymentRecordReviewId) === String(recordReviewId)
    && ACTIVE_STATUSES.includes(item.voucherStatus)
  )) || null
}

export function writePaymentVoucherDraftLog(action, payload = {}) {
  addOperationLog({
    module: '付款凭证草稿',
    action,
    targetType: payload.targetType || 'paymentVoucherDraft',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源单据：${payload.sourceNo || '-'}`,
      `目标单据：${payload.targetNo || '-'}`,
      `结果：${payload.result || '成功'}`,
      '边界：本动作只处理付款凭证草稿，不生成正式财务凭证，不写总账，不过账，不做付款核销。',
    ].join('；'),
  })
}

export function getPaymentVoucherDraftState() {
  return clone(state)
}

export function savePaymentVoucherDraftState(nextState = {}) {
  state = normalizeState(nextState)
  persist()
  return getPaymentVoucherDraftState()
}

export function resetPaymentVoucherDraftState() {
  state = defaultState()
  persist()
  return getPaymentVoucherDraftState()
}

export function listPaymentVoucherDrafts() {
  return clone(state.paymentVoucherDrafts)
}

export function getPaymentVoucherDraftById(id) {
  const item = byId(id)
  return item ? clone(item) : null
}

export function markPaymentVoucherDraftReviewGenerated(id, review = {}) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款凭证草稿。' }
  Object.assign(current, {
    paymentVoucherReviewGenerated: true,
    targetPaymentVoucherReviewId: review.id || current.targetPaymentVoucherReviewId || '',
    targetPaymentVoucherReviewNo: review.voucherReviewNo || current.targetPaymentVoucherReviewNo || '',
    targetModule: 'paymentVoucherReview',
    voucherReviewStatus: review.voucherReviewStatus || 'pending',
    voucherReviewResult: review.voucherReviewResult || current.voucherReviewResult || 'notReviewed',
    paymentVoucherReviewGeneratedAt: current.paymentVoucherReviewGeneratedAt || nowText(),
    updatedAt: nowText(),
  })
  persist()
  writePaymentVoucherDraftLog('回写付款凭证复核任务', {
    sourceNo: current.voucherDraftNo,
    targetId: current.targetPaymentVoucherReviewId,
    targetNo: current.targetPaymentVoucherReviewNo,
    result: '已生成付款凭证复核任务；不生成正式凭证、不写总账。',
  })
  return { success: true, draft: clone(current) }
}

export function markPaymentVoucherDraftReviewStatus(id, review = {}) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款凭证草稿。' }
  const next = {
    paymentVoucherReviewGenerated: true,
    targetPaymentVoucherReviewId: review.id || current.targetPaymentVoucherReviewId || '',
    targetPaymentVoucherReviewNo: review.voucherReviewNo || current.targetPaymentVoucherReviewNo || '',
    targetModule: 'paymentVoucherReview',
    voucherReviewStatus: review.voucherReviewStatus || current.voucherReviewStatus || '',
    voucherReviewResult: review.voucherReviewResult || current.voucherReviewResult || '',
    voucherReviewerId: review.reviewerId || current.voucherReviewerId || '',
    voucherReviewerName: review.reviewerName || current.voucherReviewerName || '',
    voucherReviewerRole: review.reviewerRole || current.voucherReviewerRole || '',
    voucherReviewerSource: review.reviewerSource || current.voucherReviewerSource || '',
    voucherReviewedAt: review.reviewedAt || current.voucherReviewedAt || '',
    ledgerStatus: 'notPosted',
    updatedAt: nowText(),
  }
  if (review.voucherReviewStatus === 'passed') next.voucherStatus = 'reviewed'
  if (review.voucherReviewStatus === 'rejected') next.voucherStatus = 'rejected'
  if (review.voucherReviewStatus === 'cancelled') next.voucherReviewStatus = 'cancelled'
  Object.assign(current, next)
  persist()
  writePaymentVoucherDraftLog('同步付款凭证复核状态', {
    sourceNo: current.voucherDraftNo,
    targetId: current.targetPaymentVoucherReviewId,
    targetNo: current.targetPaymentVoucherReviewNo,
    result: `复核状态已同步为 ${current.voucherReviewStatus || '-'}；仍不写总账、不过账。`,
  })
  return { success: true, draft: clone(current) }
}

export function isPaymentVoucherDraftGenerated(paymentRecordReviewId) {
  const existing = activeByRecordReviewId(paymentRecordReviewId)
  return existing ? clone(existing) : null
}

function sourceAmount(review = {}) {
  return toSafeAmount(review.executionAmount ?? review.totalPayableAmount ?? review.unpaidAmount)
}

function canCreateFromRecordReview(review = {}) {
  if (!review?.id) return '未找到付款记录复核。'
  if (review.reviewStatus !== 'passed' || review.reviewResult !== 'passed') return '只有付款记录复核通过的记录可以生成付款凭证草稿。'
  if (sourceAmount(review) <= 0) return '付款凭证草稿金额必须大于 0。'
  if (!hasText(review.supplierName)) return '供应商缺失，不能生成付款凭证草稿。'
  if (!hasText(review.sourcePaymentExecutionNo)) return '来源付款执行草稿缺失，不能生成付款凭证草稿。'
  if (!hasText(review.sourceApDraftNo) && !hasText(review.sourcePayablePrepareNo)) return '应付来源缺失，不能生成付款凭证草稿。'
  if (review.ledgerStatus === 'posted') return '该记录已过账，不能生成付款凭证草稿。'
  if (review.voucherStatus === 'formalGenerated') return '该记录已生成正式凭证，不能重复生成草稿。'
  if (activeByRecordReviewId(review.id)) return '该付款记录复核已生成付款凭证草稿，不能重复生成。'
  return ''
}

export function getPaymentVoucherDraftSourcesFromRecordReviews() {
  return listPaymentRecordReviews().map((review) => {
    const existing = activeByRecordReviewId(review.id)
    const disabledReason = existing ? '该付款记录复核已生成付款凭证草稿，不能重复生成。' : canCreateFromRecordReview(review)
    return {
      ...review,
      paymentVoucherDraftGenerated: Boolean(existing),
      targetPaymentVoucherDraftId: existing?.id || '',
      targetPaymentVoucherDraftNo: existing?.voucherDraftNo || '',
      canGeneratePaymentVoucherDraft: !disabledReason,
      disabledReason,
    }
  })
}

export function validateVoucherDraftBalance(draft = {}) {
  const debitCents = Math.round(toSafeAmount(draft.debitAmount) * 100)
  const creditCents = Math.round(toSafeAmount(draft.creditAmount) * 100)
  if (debitCents <= 0 || creditCents <= 0) {
    return { result: 'blocked', level: 'blocked', message: '借方金额和贷方金额必须大于 0。' }
  }
  if (debitCents !== creditCents) {
    return { result: 'blocked', level: 'blocked', message: '借贷金额不平衡，不能提交凭证复核。' }
  }
  return { result: 'passed', level: 'info', message: '借贷金额平衡。' }
}

export function validateVoucherDraftSource(draft = {}) {
  const required = [
    draft.sourcePaymentRecordReviewNo,
    draft.sourcePaymentExecutionNo,
    draft.sourceApDraftNo || draft.sourcePayablePrepareNo,
    draft.sourcePurchaseOrderNo || draft.rootRequestNo,
  ]
  if (required.some((value) => !hasText(value))) {
    return { result: 'blocked', level: 'blocked', message: '来源链缺失，请检查付款记录复核、付款执行、应付来源和采购来源。' }
  }
  return { result: 'passed', level: 'info', message: '来源链检查通过。' }
}

export function validateVoucherDraftAccounts(draft = {}) {
  const missing = (draft.lines || []).some((line) => !hasText(line.accountCode) || !hasText(line.accountName))
  if (missing) return { result: 'warning', level: 'warning', message: '科目未完全配置，当前使用草稿占位科目，后续需接入正式会计科目体系。' }
  return { result: 'passed', level: 'info', message: '科目草案完整。' }
}

export function buildVoucherDraftRiskItems(draft = {}) {
  const amount = toSafeAmount(draft.totalVoucherAmount)
  const sourceCheck = validateVoucherDraftSource(draft)
  const balanceCheck = validateVoucherDraftBalance(draft)
  const accountCheck = validateVoucherDraftAccounts(draft)
  const duplicate = activeByRecordReviewId(draft.sourcePaymentRecordReviewId)
  const duplicateIsSelf = duplicate && String(duplicate.id) === String(draft.id)
  const items = [
    {
      itemCode: 'sourceReview',
      itemName: '来源付款记录复核检查',
      result: draft.sourcePaymentRecordReviewNo ? 'passed' : 'blocked',
      level: draft.sourcePaymentRecordReviewNo ? 'info' : 'blocked',
      message: draft.sourcePaymentRecordReviewNo ? '来源付款记录复核存在。' : '缺少来源付款记录复核。',
    },
    {
      itemCode: 'sourceChain',
      itemName: '来源链完整性检查',
      ...sourceCheck,
    },
    {
      itemCode: 'amount',
      itemName: '金额检查',
      result: amount > 0 ? 'passed' : 'blocked',
      level: amount > 0 ? 'info' : 'blocked',
      message: amount > 0 ? '金额检查通过。' : '付款凭证草稿金额必须大于 0。',
    },
    {
      itemCode: 'balance',
      itemName: '借贷平衡检查',
      ...balanceCheck,
    },
    {
      itemCode: 'account',
      itemName: '科目完整性检查',
      ...accountCheck,
    },
    {
      itemCode: 'accountingPeriod',
      itemName: '会计期间检查',
      result: hasText(draft.accountingPeriod) ? 'passed' : 'warning',
      level: hasText(draft.accountingPeriod) ? 'info' : 'warning',
      message: hasText(draft.accountingPeriod) ? '会计期间已填写。' : '会计期间为空，后续需接入正式会计期间。',
    },
    {
      itemCode: 'duplicate',
      itemName: '防重复凭证检查',
      result: !duplicate || duplicateIsSelf ? 'passed' : 'blocked',
      level: !duplicate || duplicateIsSelf ? 'info' : 'blocked',
      message: !duplicate || duplicateIsSelf ? '未发现重复未关闭凭证草稿。' : '同一付款记录复核已存在未关闭付款凭证草稿。',
    },
    {
      itemCode: 'ledgerBoundary',
      itemName: '总账边界检查',
      result: draft.ledgerStatus === 'notPosted' ? 'passed' : 'blocked',
      level: draft.ledgerStatus === 'notPosted' ? 'info' : 'blocked',
      message: draft.ledgerStatus === 'notPosted' ? '本轮不写总账，不过账。' : '草稿阶段不得写总账或过账。',
    },
  ]
  const hasBlocked = items.some((item) => item.level === 'blocked')
  const hasWarning = items.some((item) => item.level === 'warning')
  return {
    riskItems: items,
    riskStatus: hasBlocked ? 'blocked' : (hasWarning ? 'warning' : 'passed'),
    riskLevel: hasBlocked ? 'blocked' : (hasWarning ? 'warning' : 'low'),
  }
}

function buildDraftLines(review = {}, amount = 0) {
  const base = {
    sourcePaymentRecordReviewLineId: (review.lines || [])[0]?.id || '',
    sourcePurchaseOrderNo: review.sourcePurchaseOrderNo || '',
    sourceReceiveNo: review.sourceReceiveNo || '',
    sourceInspectionNo: review.sourceInspectionNo || '',
    sourceInventoryTransactionNo: (review.sourceInventoryTransactionNos || [])[0] || '',
    rootRequestNo: review.rootRequestNo || '',
  }
  return [
    normalizeLine({
      ...base,
      lineNo: 1,
      direction: 'debit',
      accountCode: '2202',
      accountName: '应付账款',
      amount,
      cashFlowItem: '',
      remark: '借方草稿分录：冲减供应商应付账款。当前科目为草稿占位，后续需接入正式会计科目体系。',
    }),
    normalizeLine({
      ...base,
      lineNo: 2,
      direction: 'credit',
      accountCode: '1002',
      accountName: '银行存款',
      amount,
      cashFlowItem: '购买商品、接受劳务支付的现金',
      remark: '贷方草稿分录：付款资金流出。当前不生成正式凭证、不写总账。',
    }),
  ]
}

function buildDraftFromRecordReview(review = {}) {
  const amount = sourceAmount(review)
  const lines = buildDraftLines(review, amount)
  const draft = normalizeDraft({
    sourcePaymentRecordReviewId: review.id,
    sourcePaymentRecordReviewNo: review.paymentRecordReviewNo,
    sourcePaymentExecutionNo: review.sourcePaymentExecutionNo,
    sourceRiskReviewNo: review.sourceRiskReviewNo,
    sourcePaymentOrderDraftNo: review.sourcePaymentOrderDraftNo,
    sourcePaymentPrepareNo: review.sourcePaymentPrepareNo,
    sourcePaymentDraftNo: review.sourcePaymentDraftNo,
    sourceApDraftNo: review.sourceApDraftNo,
    sourceInvoicePrepareNo: review.sourceInvoicePrepareNo,
    sourcePayableCheckNo: review.sourcePayableCheckNo,
    sourcePayablePrepareNo: review.sourcePayablePrepareNo,
    supplierId: review.supplierId,
    supplierName: review.supplierName,
    sourcePurchaseOrderNo: review.sourcePurchaseOrderNo,
    sourceReceiveNo: review.sourceReceiveNo,
    sourceInspectionNo: review.sourceInspectionNo,
    sourceInventoryTransactionNos: review.sourceInventoryTransactionNos || [],
    rootRequestNo: review.rootRequestNo,
    totalVoucherAmount: amount,
    debitAmount: amount,
    creditAmount: amount,
    differenceAmount: 0,
    voucherStatus: 'draft',
    reviewStatus: 'notSubmitted',
    ledgerStatus: 'notPosted',
    lines,
  })
  const risk = buildVoucherDraftRiskItems(draft)
  return normalizeDraft({ ...draft, ...risk })
}

export function createPaymentVoucherDraftFromRecordReview(paymentRecordReviewId) {
  const review = getPaymentRecordReviewById(paymentRecordReviewId)
  if (!review) return { success: false, error: '未找到付款记录复核。' }
  const existing = activeByRecordReviewId(review.id)
  if (existing) {
    writePaymentVoucherDraftLog('防重复生成付款凭证草稿', {
      sourceNo: review.paymentRecordReviewNo,
      targetId: existing.id,
      targetNo: existing.voucherDraftNo,
      result: '已存在未关闭付款凭证草稿，无需重复生成。',
    })
    return {
      success: true,
      alreadyDone: true,
      draft: clone(existing),
      message: '该付款记录复核已生成付款凭证草稿，不能重复生成。',
    }
  }
  const disabledReason = canCreateFromRecordReview(review)
  if (disabledReason) return { success: false, error: disabledReason }
  const draft = buildDraftFromRecordReview(review)
  state.paymentVoucherDrafts.unshift(draft)
  persist()
  markPaymentRecordReviewPaymentVoucherDraftGenerated(review.id, draft)
  writePaymentVoucherDraftLog('生成付款凭证草稿', {
    sourceNo: review.paymentRecordReviewNo,
    targetId: draft.id,
    targetNo: draft.voucherDraftNo,
    result: '已生成付款凭证草稿；不是正式财务凭证，不写总账。',
  })
  return { success: true, draft: clone(draft) }
}

export function updatePaymentVoucherDraft(id, patch = {}) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款凭证草稿。' }
  Object.assign(current, patch, { updatedAt: nowText() })
  const risk = buildVoucherDraftRiskItems(current)
  Object.assign(current, risk)
  persist()
  writePaymentVoucherDraftLog('更新付款凭证草稿', {
    targetId: current.id,
    targetNo: current.voucherDraftNo,
    result: '已更新草稿字段并重新执行风险检查。',
  })
  return { success: true, draft: clone(current) }
}

export function submitPaymentVoucherDraftReview(id) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款凭证草稿。' }
  if (current.voucherStatus === 'readyForReview') {
    return {
      success: true,
      alreadyDone: true,
      draft: clone(current),
      message: '该付款凭证草稿已提交凭证复核，无需重复提交。',
    }
  }
  if (current.voucherStatus !== 'draft') return { success: false, error: '只有草稿状态可以提交凭证复核。' }
  const risk = buildVoucherDraftRiskItems(current)
  Object.assign(current, risk)
  if (risk.riskStatus === 'blocked') {
    persist()
    return { success: false, error: '存在阻断风险，不能提交凭证复核。', draft: clone(current) }
  }
  Object.assign(current, {
    voucherStatus: 'readyForReview',
    reviewStatus: 'pending',
    ledgerStatus: 'notPosted',
    submittedAt: nowText(),
    submittedBy: '当前制单人',
    reviewedAt: '',
    updatedAt: nowText(),
  })
  persist()
  markPaymentRecordReviewPaymentVoucherDraftStatus(current.sourcePaymentRecordReviewId, current)
  writePaymentVoucherDraftLog('提交付款凭证草稿复核', {
    targetId: current.id,
    targetNo: current.voucherDraftNo,
    result: '已提交到待凭证复核；仍未生成正式凭证，不写总账。',
  })
  return { success: true, draft: clone(current) }
}

export function cancelPaymentVoucherDraft(id) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款凭证草稿。' }
  if (current.voucherStatus === 'cancelled') {
    return {
      success: true,
      alreadyDone: true,
      draft: clone(current),
      message: '该付款凭证草稿已取消，无需重复取消。',
    }
  }
  if (current.voucherStatus !== 'draft') return { success: false, error: '只有草稿状态可以取消；待复核状态本轮不继续处理。' }
  Object.assign(current, {
    voucherStatus: 'cancelled',
    reviewStatus: 'notSubmitted',
    cancelledBy: '当前制单人',
    cancelledAt: nowText(),
    updatedAt: nowText(),
  })
  persist()
  markPaymentRecordReviewPaymentVoucherDraftStatus(current.sourcePaymentRecordReviewId, current)
  writePaymentVoucherDraftLog('取消付款凭证草稿', {
    targetId: current.id,
    targetNo: current.voucherDraftNo,
    result: '已取消付款凭证草稿；不影响前序付款记录复核。',
  })
  return { success: true, draft: clone(current) }
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
    const draft = outcome.draft || {}
    if (outcome.alreadyDone) {
      result.alreadyDoneCount += 1
      result.alreadyDoneItems.push({ id, no, status: draft.voucherStatus })
    } else {
      result.successCount += 1
      result.successItems.push({ id, no, status: draft.voucherStatus })
    }
  })
  result.nextSuggestion = result.failedCount
    ? '请按失败原因处理后再重试；本批量动作不会生成正式财务凭证或写总账。'
    : '本批量动作已完成或已达成；下一步可查看草稿或提交凭证复核。'
  writePaymentVoucherDraftLog(label, {
    targetType: 'batchPaymentVoucherDraft',
    targetId: label,
    result: `成功 ${result.successCount} 条，已达成 ${result.alreadyDoneCount} 条，失败 ${result.failedCount} 条。`,
  })
  return result
}

export function batchCreatePaymentVoucherDraftsFromRecordReviews(ids = []) {
  return batchResult(ids, createPaymentVoucherDraftFromRecordReview, '批量生成付款凭证草稿', (id) => getPaymentRecordReviewById(id)?.paymentRecordReviewNo || id)
}

export function batchSubmitPaymentVoucherDraftReview(ids = []) {
  return batchResult(ids, submitPaymentVoucherDraftReview, '批量提交凭证复核', (id) => byId(id)?.voucherDraftNo || id)
}

export function batchCancelPaymentVoucherDrafts(ids = []) {
  return batchResult(ids, cancelPaymentVoucherDraft, '批量取消付款凭证草稿', (id) => byId(id)?.voucherDraftNo || id)
}

export function getPaymentVoucherDraftStatusLabel(status) {
  return {
    draft: '凭证草稿',
    readyForReview: '待凭证复核',
    reviewed: '凭证已复核',
    rejected: '复核退回',
    cancelled: '已取消',
  }[status] || status || '-'
}

export function getPaymentVoucherDraftStatusType(status) {
  return {
    draft: 'info',
    readyForReview: 'warning',
    reviewed: 'success',
    rejected: 'danger',
    cancelled: 'info',
  }[status] || 'info'
}

export function getPaymentVoucherReviewStatusLabel(status) {
  return {
    notSubmitted: '未提交',
    pending: '待复核',
    reviewing: '复核中',
    passed: '复核通过',
    reviewed: '已复核',
    rejected: '复核退回',
    cancelled: '取消复核',
  }[status] || status || '-'
}

export function getPaymentVoucherLedgerStatusLabel(status) {
  return {
    notPosted: '未过账',
    posted: '已过账',
  }[status] || status || '-'
}

export function getPaymentVoucherRiskLevelLabel(level) {
  return {
    pending: '待检查',
    low: '低风险',
    warning: '有警告',
    blocked: '阻断',
  }[level] || level || '-'
}

export function getPaymentVoucherRiskLevelType(level) {
  return {
    low: 'success',
    warning: 'warning',
    blocked: 'danger',
    pending: 'info',
  }[level] || 'info'
}
