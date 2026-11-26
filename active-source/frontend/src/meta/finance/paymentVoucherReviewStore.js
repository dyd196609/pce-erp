import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  getPaymentVoucherDraftById,
  listPaymentVoucherDrafts,
  markPaymentVoucherDraftReviewGenerated,
  markPaymentVoucherDraftReviewStatus,
} from './paymentVoucherDraftStore.js'

const STORAGE_KEY = 'payment-voucher-review-state-v1'
const ACTIVE_REVIEW_STATUSES = ['pending', 'reviewing', 'passed', 'rejected']

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

function toSafeAmount(value) {
  const normalized = Number(String(value ?? 0).replace(/,/g, '').trim())
  if (!Number.isFinite(normalized)) return 0
  return Math.round(normalized * 100) / 100
}

function hasText(value) {
  return String(value || '').trim().length > 0
}

function defaultState() {
  return { paymentVoucherReviews: [] }
}

function normalizeLine(line = {}, index = 0, source = {}) {
  return {
    id: line.id || createId('pvrl'),
    lineNo: line.lineNo || index + 1,
    direction: line.direction || 'debit',
    accountCode: line.accountCode || '',
    accountName: line.accountName || '',
    amount: toSafeAmount(line.amount),
    cashFlowItem: line.cashFlowItem || '',
    sourcePurchaseOrderNo: line.sourcePurchaseOrderNo || source.sourcePurchaseOrderNo || '',
    sourceReceiveNo: line.sourceReceiveNo || source.sourceReceiveNo || '',
    sourceInspectionNo: line.sourceInspectionNo || source.sourceInspectionNo || '',
    sourceInventoryTransactionNo: line.sourceInventoryTransactionNo || (source.sourceInventoryTransactionNos || [])[0] || '',
    rootRequestNo: line.rootRequestNo || source.rootRequestNo || '',
    remark: line.remark || '',
  }
}

function normalizeReview(item = {}) {
  const lines = Array.isArray(item.lines) ? item.lines.map((line, index) => normalizeLine(line, index, item)) : []
  const debitAmount = toSafeAmount(item.debitAmount ?? lines.filter((line) => line.direction === 'debit').reduce((sum, line) => sum + toSafeAmount(line.amount), 0))
  const creditAmount = toSafeAmount(item.creditAmount ?? lines.filter((line) => line.direction === 'credit').reduce((sum, line) => sum + toSafeAmount(line.amount), 0))
  return {
    id: item.id || createId('pvr'),
    voucherReviewNo: item.voucherReviewNo || createNo('PVR'),
    sourceVoucherDraftId: item.sourceVoucherDraftId || '',
    sourceVoucherDraftNo: item.sourceVoucherDraftNo || '',
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
    voucherDate: item.voucherDate || '',
    accountingPeriod: item.accountingPeriod || '',
    debitAmount,
    creditAmount,
    differenceAmount: toSafeAmount(item.differenceAmount ?? debitAmount - creditAmount),
    voucherReviewStatus: item.voucherReviewStatus || 'pending',
    voucherReviewResult: item.voucherReviewResult || 'notReviewed',
    voucherReviewOpinion: item.voucherReviewOpinion || '',
    reviewerId: item.reviewerId || '',
    reviewerName: item.reviewerName || '',
    reviewerRole: item.reviewerRole || '',
    reviewerSource: item.reviewerSource || '',
    reviewedAt: item.reviewedAt || '',
    voucherStatus: item.voucherStatus || 'readyForReview',
    formalVoucherGenerated: Boolean(item.formalVoucherGenerated),
    targetFormalVoucherId: item.targetFormalVoucherId || '',
    targetFormalVoucherNo: item.targetFormalVoucherNo || '',
    targetModule: item.targetModule || '',
    formalVoucherStatus: item.formalVoucherStatus || '',
    postingStatus: item.postingStatus || 'notPosted',
    paymentWriteOffStatus: item.paymentWriteOffStatus || 'notWrittenOff',
    formalVoucherGeneratedAt: item.formalVoucherGeneratedAt || '',
    ledgerStatus: item.ledgerStatus || 'notPosted',
    riskLevel: item.riskLevel || 'pending',
    riskStatus: item.riskStatus || 'pending',
    riskItems: Array.isArray(item.riskItems) ? item.riskItems : [],
    createdAt: item.createdAt || nowText(),
    startedAt: item.startedAt || '',
    cancelledAt: item.cancelledAt || '',
    updatedAt: item.updatedAt || nowText(),
    lines,
    operationLogs: Array.isArray(item.operationLogs) ? item.operationLogs : [],
  }
}

function normalizeState(raw = {}) {
  return {
    paymentVoucherReviews: (raw.paymentVoucherReviews || []).map(normalizeReview),
  }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[PAYMENT VOUCHER REVIEW STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function byId(id) {
  return state.paymentVoucherReviews.find((item) => String(item.id) === String(id)) || null
}

function activeByVoucherDraftId(voucherDraftId) {
  return state.paymentVoucherReviews.find((item) => (
    String(item.sourceVoucherDraftId) === String(voucherDraftId)
    && ACTIVE_REVIEW_STATUSES.includes(item.voucherReviewStatus)
  )) || null
}

function resolveReviewer() {
  return {
    reviewerId: 'LOCAL-VOUCHER-REVIEWER',
    reviewerName: '当前凭证复核人',
    reviewerRole: '付款凭证复核',
    reviewerSource: 'localDemo',
  }
}

export function writePaymentVoucherReviewLog(action, payload = {}) {
  addOperationLog({
    module: '付款凭证复核',
    action,
    targetType: payload.targetType || 'paymentVoucherReview',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源单据：${payload.sourceNo || '-'}`,
      `目标单据：${payload.targetNo || '-'}`,
      `结果：${payload.result || '成功'}`,
      '边界：本动作只处理付款凭证草稿复核，不生成正式财务凭证，不写总账，不过账，不做付款核销。',
    ].join('；'),
  })
}

export function getPaymentVoucherReviewState() {
  return clone(state)
}

export function savePaymentVoucherReviewState(nextState = {}) {
  state = normalizeState(nextState)
  persist()
  return getPaymentVoucherReviewState()
}

export function resetPaymentVoucherReviewState() {
  state = defaultState()
  persist()
  return getPaymentVoucherReviewState()
}

export function listPaymentVoucherReviews() {
  return clone(state.paymentVoucherReviews)
}

export function getPaymentVoucherReviewById(id) {
  const item = byId(id)
  return item ? clone(item) : null
}

export function isPaymentVoucherReviewGenerated(voucherDraftId) {
  const existing = activeByVoucherDraftId(voucherDraftId)
  return existing ? clone(existing) : null
}

export function markPaymentVoucherReviewFormalVoucherGenerated(id, formalVoucher = {}) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款凭证复核任务。' }
  Object.assign(current, {
    formalVoucherGenerated: true,
    targetFormalVoucherId: formalVoucher.id || current.targetFormalVoucherId || '',
    targetFormalVoucherNo: formalVoucher.formalVoucherNo || current.targetFormalVoucherNo || '',
    targetModule: 'formalPaymentVoucher',
    formalVoucherStatus: formalVoucher.formalVoucherStatus || 'generated',
    postingStatus: formalVoucher.postingStatus || 'notPosted',
    ledgerStatus: formalVoucher.ledgerStatus || 'notWritten',
    paymentWriteOffStatus: formalVoucher.paymentWriteOffStatus || 'notWrittenOff',
    formalVoucherGeneratedAt: current.formalVoucherGeneratedAt || nowText(),
    updatedAt: nowText(),
  })
  persist()
  writePaymentVoucherReviewLog('回写正式付款凭证生成状态', {
    sourceNo: current.voucherReviewNo,
    targetId: current.targetFormalVoucherId,
    targetNo: current.targetFormalVoucherNo,
    result: '已生成正式付款凭证对象；仍未过账、未写总账、未核销。',
  })
  return { success: true, review: clone(current) }
}

export function markPaymentVoucherReviewFormalVoucherCancelled(id, formalVoucher = {}) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款凭证复核任务。' }
  Object.assign(current, {
    formalVoucherGenerated: false,
    targetFormalVoucherId: formalVoucher.id || current.targetFormalVoucherId || '',
    targetFormalVoucherNo: formalVoucher.formalVoucherNo || current.targetFormalVoucherNo || '',
    targetModule: 'formalPaymentVoucher',
    formalVoucherStatus: 'cancelled',
    postingStatus: formalVoucher.postingStatus || current.postingStatus || 'notPosted',
    ledgerStatus: formalVoucher.ledgerStatus || current.ledgerStatus || 'notWritten',
    paymentWriteOffStatus: formalVoucher.paymentWriteOffStatus || current.paymentWriteOffStatus || 'notWrittenOff',
    updatedAt: nowText(),
  })
  persist()
  writePaymentVoucherReviewLog('正式付款凭证取消状态回写', {
    sourceNo: current.voucherReviewNo,
    targetId: current.targetFormalVoucherId,
    targetNo: current.targetFormalVoucherNo,
    result: '正式付款凭证已取消；来源页不再视为未关闭正式凭证，可按规则重新生成。',
  })
  return { success: true, review: clone(current) }
}

export function validateVoucherReviewSource(review = {}) {
  const required = [
    review.sourceVoucherDraftNo,
    review.sourcePaymentRecordReviewNo,
    review.sourcePaymentExecutionNo,
    review.sourceApDraftNo || review.sourcePayablePrepareNo,
    review.sourcePurchaseOrderNo || review.rootRequestNo,
  ]
  if (required.some((value) => !hasText(value))) {
    return { result: 'blocked', level: 'blocked', message: '来源链缺失，请检查凭证草稿、付款记录复核、付款执行、应付来源和采购来源。' }
  }
  return { result: 'passed', level: 'info', message: '来源链检查通过。' }
}

export function validateVoucherReviewBalance(review = {}) {
  const debitCents = Math.round(toSafeAmount(review.debitAmount) * 100)
  const creditCents = Math.round(toSafeAmount(review.creditAmount) * 100)
  const diffCents = Math.round(toSafeAmount(review.differenceAmount) * 100)
  if (debitCents <= 0 || creditCents <= 0) {
    return { result: 'blocked', level: 'blocked', message: '借方金额和贷方金额必须大于 0。' }
  }
  if (debitCents !== creditCents || diffCents !== 0) {
    return { result: 'blocked', level: 'blocked', message: '借贷金额不平衡，不能通过凭证复核。' }
  }
  return { result: 'passed', level: 'info', message: '借贷金额平衡，差异金额为 0。' }
}

export function validateVoucherReviewAccounts(review = {}) {
  const missing = (review.lines || []).some((line) => !hasText(line.accountCode) || !hasText(line.accountName))
  if (missing) return { result: 'warning', level: 'warning', message: '科目未完全配置，当前仍为草稿占位科目，后续需接入正式会计科目体系。' }
  return { result: 'passed', level: 'info', message: '凭证分录科目草案完整。' }
}

export function validateVoucherReviewPeriod(review = {}) {
  if (!hasText(review.voucherDate) || !hasText(review.accountingPeriod)) {
    return { result: 'warning', level: 'warning', message: '凭证日期或会计期间缺失，后续需接入正式会计期间管理。' }
  }
  return { result: 'passed', level: 'info', message: '凭证日期和会计期间已填写。' }
}

export function validateVoucherReviewLedgerBoundary(review = {}) {
  if (review.ledgerStatus !== 'notPosted') {
    return { result: 'blocked', level: 'blocked', message: '凭证复核阶段不得过账或写总账。' }
  }
  return { result: 'passed', level: 'info', message: '本轮不生成正式凭证、不写总账、不过账。' }
}

export function buildPaymentVoucherReviewRiskItems(review = {}) {
  const sourceCheck = validateVoucherReviewSource(review)
  const balanceCheck = validateVoucherReviewBalance(review)
  const accountCheck = validateVoucherReviewAccounts(review)
  const periodCheck = validateVoucherReviewPeriod(review)
  const ledgerCheck = validateVoucherReviewLedgerBoundary(review)
  const duplicate = activeByVoucherDraftId(review.sourceVoucherDraftId)
  const duplicateIsSelf = duplicate && String(duplicate.id) === String(review.id)
  const amount = Math.round(Math.max(toSafeAmount(review.debitAmount), toSafeAmount(review.creditAmount)) * 100)
  const items = [
    { itemCode: 'source', itemName: '来源完整性检查', ...sourceCheck },
    { itemCode: 'balance', itemName: '借贷平衡检查', ...balanceCheck },
    {
      itemCode: 'amount',
      itemName: '金额一致性检查',
      result: amount > 0 ? 'passed' : 'blocked',
      level: amount > 0 ? 'info' : 'blocked',
      message: amount > 0 ? '金额检查通过。' : '凭证复核金额必须大于 0。',
    },
    { itemCode: 'account', itemName: '科目检查', ...accountCheck },
    { itemCode: 'period', itemName: '会计期间检查', ...periodCheck },
    {
      itemCode: 'duplicate',
      itemName: '防重复复核检查',
      result: !duplicate || duplicateIsSelf ? 'passed' : 'blocked',
      level: !duplicate || duplicateIsSelf ? 'info' : 'blocked',
      message: !duplicate || duplicateIsSelf ? '未发现重复未关闭复核任务。' : '该付款凭证草稿已存在未关闭复核任务。',
    },
    {
      itemCode: 'permission',
      itemName: '权限边界检查',
      result: 'warning',
      level: 'warning',
      message: '当前使用本地演示复核人，后续需接入正式登录用户、岗位权限和审批流。',
    },
    { itemCode: 'ledgerBoundary', itemName: '过账边界检查', ...ledgerCheck },
  ]
  const hasBlocked = items.some((item) => item.level === 'blocked')
  const hasWarning = items.some((item) => item.level === 'warning')
  return {
    riskItems: items,
    riskStatus: hasBlocked ? 'blocked' : (hasWarning ? 'warning' : 'passed'),
    riskLevel: hasBlocked ? 'blocked' : (hasWarning ? 'warning' : 'low'),
  }
}

function canCreateFromVoucherDraft(draft = {}) {
  if (!draft?.id) return '未找到付款凭证草稿。'
  if (draft.voucherStatus !== 'readyForReview') return '只有“待凭证复核”的付款凭证草稿可以生成复核任务。'
  if (draft.reviewStatus !== 'pending') return '付款凭证草稿复核状态必须为待复核。'
  if (draft.ledgerStatus !== 'notPosted') return '已过账记录不能进入付款凭证复核。'
  if (toSafeAmount(draft.totalVoucherAmount) <= 0) return '凭证金额必须大于 0。'
  if (Math.round(toSafeAmount(draft.debitAmount) * 100) !== Math.round(toSafeAmount(draft.creditAmount) * 100)) return '借贷金额不平衡，不能生成复核任务。'
  if (Math.round(toSafeAmount(draft.differenceAmount) * 100) !== 0) return '差异金额必须为 0。'
  if (!hasText(draft.sourcePaymentRecordReviewNo)) return '来源付款记录复核缺失，不能生成复核任务。'
  if (activeByVoucherDraftId(draft.id)) return '该付款凭证草稿已生成付款凭证复核任务，不能重复生成。'
  return ''
}

export function getPaymentVoucherReviewSourcesFromVoucherDrafts() {
  return listPaymentVoucherDrafts().map((draft) => {
    const existing = activeByVoucherDraftId(draft.id)
    const disabledReason = existing ? '该付款凭证草稿已生成付款凭证复核任务，不能重复生成。' : canCreateFromVoucherDraft(draft)
    return {
      ...draft,
      paymentVoucherReviewGenerated: Boolean(existing),
      targetPaymentVoucherReviewId: existing?.id || '',
      targetPaymentVoucherReviewNo: existing?.voucherReviewNo || '',
      canGeneratePaymentVoucherReview: !disabledReason,
      disabledReason,
    }
  })
}

function buildReviewFromVoucherDraft(draft = {}) {
  const review = normalizeReview({
    sourceVoucherDraftId: draft.id,
    sourceVoucherDraftNo: draft.voucherDraftNo,
    sourcePaymentRecordReviewNo: draft.sourcePaymentRecordReviewNo,
    sourcePaymentExecutionNo: draft.sourcePaymentExecutionNo,
    sourceRiskReviewNo: draft.sourceRiskReviewNo,
    sourcePaymentOrderDraftNo: draft.sourcePaymentOrderDraftNo,
    sourcePaymentPrepareNo: draft.sourcePaymentPrepareNo,
    sourcePaymentDraftNo: draft.sourcePaymentDraftNo,
    sourceApDraftNo: draft.sourceApDraftNo,
    sourceInvoicePrepareNo: draft.sourceInvoicePrepareNo,
    sourcePayableCheckNo: draft.sourcePayableCheckNo,
    sourcePayablePrepareNo: draft.sourcePayablePrepareNo,
    supplierId: draft.supplierId,
    supplierName: draft.supplierName,
    sourcePurchaseOrderNo: draft.sourcePurchaseOrderNo,
    sourceReceiveNo: draft.sourceReceiveNo,
    sourceInspectionNo: draft.sourceInspectionNo,
    sourceInventoryTransactionNos: draft.sourceInventoryTransactionNos || [],
    rootRequestNo: draft.rootRequestNo,
    voucherDate: draft.voucherDate,
    accountingPeriod: draft.accountingPeriod,
    debitAmount: draft.debitAmount,
    creditAmount: draft.creditAmount,
    differenceAmount: draft.differenceAmount,
    voucherReviewStatus: 'pending',
    voucherReviewResult: 'notReviewed',
    voucherStatus: 'readyForReview',
    ledgerStatus: 'notPosted',
    lines: draft.lines || [],
  })
  const risk = buildPaymentVoucherReviewRiskItems(review)
  return normalizeReview({ ...review, ...risk })
}

export function createPaymentVoucherReviewFromVoucherDraft(voucherDraftId) {
  const draft = getPaymentVoucherDraftById(voucherDraftId)
  if (!draft) return { success: false, error: '未找到付款凭证草稿。' }
  const existing = activeByVoucherDraftId(draft.id)
  if (existing) {
    writePaymentVoucherReviewLog('防重复生成付款凭证复核任务', {
      sourceNo: draft.voucherDraftNo,
      targetId: existing.id,
      targetNo: existing.voucherReviewNo,
      result: '已存在未关闭付款凭证复核任务，无需重复生成。',
    })
    return {
      success: true,
      alreadyDone: true,
      review: clone(existing),
      message: '该付款凭证草稿已生成付款凭证复核任务，不能重复生成。',
    }
  }
  const disabledReason = canCreateFromVoucherDraft(draft)
  if (disabledReason) return { success: false, error: disabledReason }
  const review = buildReviewFromVoucherDraft(draft)
  state.paymentVoucherReviews.unshift(review)
  persist()
  markPaymentVoucherDraftReviewGenerated(draft.id, review)
  writePaymentVoucherReviewLog('生成付款凭证复核任务', {
    sourceNo: draft.voucherDraftNo,
    targetId: review.id,
    targetNo: review.voucherReviewNo,
    result: '已生成付款凭证复核任务；不生成正式凭证、不写总账。',
  })
  return { success: true, review: clone(review) }
}

export function startPaymentVoucherReview(id) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款凭证复核任务。' }
  if (current.voucherReviewStatus === 'reviewing') return { success: true, alreadyDone: true, review: clone(current), message: '该付款凭证复核任务已在复核中，无需重复开始。' }
  if (!['pending', 'rejected'].includes(current.voucherReviewStatus)) return { success: false, error: '只有待复核或已退回的任务可以开始复核。' }
  Object.assign(current, {
    voucherReviewStatus: 'reviewing',
    voucherReviewResult: 'notReviewed',
    voucherReviewOpinion: current.voucherReviewStatus === 'rejected' ? current.voucherReviewOpinion : '',
    startedAt: nowText(),
    updatedAt: nowText(),
  })
  persist()
  markPaymentVoucherDraftReviewStatus(current.sourceVoucherDraftId, current)
  writePaymentVoucherReviewLog('开始付款凭证复核', { targetId: current.id, targetNo: current.voucherReviewNo, result: '已进入复核中。' })
  return { success: true, review: clone(current) }
}

export function passPaymentVoucherReview(id, opinion = '凭证草稿已通过人工复核；仍不代表正式凭证、过账、写总账或付款核销。') {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款凭证复核任务。' }
  if (current.voucherReviewStatus === 'passed') return { success: true, alreadyDone: true, review: clone(current), message: '该付款凭证复核任务已通过，无需重复通过。' }
  if (current.voucherReviewStatus !== 'reviewing') return { success: false, error: '只有复核中的任务可以复核通过。' }
  const risk = buildPaymentVoucherReviewRiskItems(current)
  Object.assign(current, risk)
  if (risk.riskStatus === 'blocked') {
    persist()
    return { success: false, error: '存在阻断风险，不能复核通过。', review: clone(current) }
  }
  const reviewer = resolveReviewer()
  Object.assign(current, {
    ...reviewer,
    voucherReviewStatus: 'passed',
    voucherReviewResult: 'passed',
    voucherReviewOpinion: opinion,
    voucherStatus: 'reviewed',
    ledgerStatus: 'notPosted',
    reviewedAt: nowText(),
    updatedAt: nowText(),
  })
  persist()
  markPaymentVoucherDraftReviewStatus(current.sourceVoucherDraftId, current)
  writePaymentVoucherReviewLog('付款凭证复核通过', { targetId: current.id, targetNo: current.voucherReviewNo, result: '复核通过；仍不生成正式凭证、不写总账。' })
  return { success: true, review: clone(current) }
}

export function rejectPaymentVoucherReview(id, opinion = '凭证草稿需退回处理。') {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款凭证复核任务。' }
  if (current.voucherReviewStatus === 'rejected') return { success: true, alreadyDone: true, review: clone(current), message: '该付款凭证复核任务已退回，无需重复退回。' }
  if (current.voucherReviewStatus !== 'reviewing') return { success: false, error: '只有复核中的任务可以退回。' }
  const reviewer = resolveReviewer()
  Object.assign(current, {
    ...reviewer,
    voucherReviewStatus: 'rejected',
    voucherReviewResult: 'rejected',
    voucherReviewOpinion: opinion,
    voucherStatus: 'rejected',
    ledgerStatus: 'notPosted',
    reviewedAt: nowText(),
    updatedAt: nowText(),
  })
  persist()
  markPaymentVoucherDraftReviewStatus(current.sourceVoucherDraftId, current)
  writePaymentVoucherReviewLog('付款凭证复核退回', { targetId: current.id, targetNo: current.voucherReviewNo, result: '复核退回；不生成正式凭证、不写总账。' })
  return { success: true, review: clone(current) }
}

export function cancelPaymentVoucherReview(id) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款凭证复核任务。' }
  if (current.voucherReviewStatus === 'cancelled') return { success: true, alreadyDone: true, review: clone(current), message: '该付款凭证复核任务已取消，无需重复取消。' }
  if (current.voucherReviewStatus === 'passed') return { success: false, error: '已通过的复核任务本轮不允许取消。' }
  Object.assign(current, {
    voucherReviewStatus: 'cancelled',
    voucherReviewResult: 'notReviewed',
    voucherStatus: 'readyForReview',
    ledgerStatus: 'notPosted',
    cancelledAt: nowText(),
    updatedAt: nowText(),
  })
  persist()
  markPaymentVoucherDraftReviewStatus(current.sourceVoucherDraftId, current)
  writePaymentVoucherReviewLog('取消付款凭证复核', { targetId: current.id, targetNo: current.voucherReviewNo, result: '已取消复核任务；不影响正式凭证，因为本轮未生成正式凭证。' })
  return { success: true, review: clone(current) }
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
    const review = outcome.review || {}
    if (outcome.alreadyDone) {
      result.alreadyDoneCount += 1
      result.alreadyDoneItems.push({ id, no, status: review.voucherReviewStatus })
    } else {
      result.successCount += 1
      result.successItems.push({ id, no, status: review.voucherReviewStatus })
    }
  })
  result.nextSuggestion = result.failedCount
    ? '请按失败原因处理后再重试；本批量动作不会生成正式凭证或写总账。'
    : '本批量动作已完成或已达成；下一步按复核状态继续处理。'
  writePaymentVoucherReviewLog(label, {
    targetType: 'batchPaymentVoucherReview',
    targetId: label,
    result: `成功 ${result.successCount} 条，已达成 ${result.alreadyDoneCount} 条，失败 ${result.failedCount} 条。`,
  })
  return result
}

export function batchCreatePaymentVoucherReviewsFromVoucherDrafts(ids = []) {
  return batchResult(ids, createPaymentVoucherReviewFromVoucherDraft, '批量生成付款凭证复核', (id) => getPaymentVoucherDraftById(id)?.voucherDraftNo || id)
}

export function batchStartPaymentVoucherReviews(ids = []) {
  return batchResult(ids, startPaymentVoucherReview, '批量开始复核', (id) => byId(id)?.voucherReviewNo || id)
}

export function batchPassPaymentVoucherReviews(ids = []) {
  return batchResult(ids, passPaymentVoucherReview, '批量复核通过', (id) => byId(id)?.voucherReviewNo || id)
}

export function batchRejectPaymentVoucherReviews(ids = []) {
  return batchResult(ids, rejectPaymentVoucherReview, '批量复核退回', (id) => byId(id)?.voucherReviewNo || id)
}

export function batchCancelPaymentVoucherReviews(ids = []) {
  return batchResult(ids, cancelPaymentVoucherReview, '批量取消复核', (id) => byId(id)?.voucherReviewNo || id)
}

export function getPaymentVoucherReviewStatusLabel(status) {
  return {
    pending: '待复核',
    reviewing: '复核中',
    passed: '复核通过',
    rejected: '复核退回',
    cancelled: '取消复核',
  }[status] || status || '-'
}

export function getPaymentVoucherReviewStatusType(status) {
  return {
    pending: 'warning',
    reviewing: 'primary',
    passed: 'success',
    rejected: 'danger',
    cancelled: 'info',
  }[status] || 'info'
}

export function getPaymentVoucherReviewResultLabel(result) {
  return {
    notReviewed: '未复核',
    passed: '通过',
    rejected: '退回',
  }[result] || result || '-'
}

export function getPaymentVoucherReviewRiskLevelLabel(level) {
  return {
    pending: '待检查',
    low: '低风险',
    warning: '有警告',
    blocked: '阻断',
  }[level] || level || '-'
}

export function getPaymentVoucherReviewRiskLevelType(level) {
  return {
    low: 'success',
    warning: 'warning',
    blocked: 'danger',
    pending: 'info',
  }[level] || 'info'
}
