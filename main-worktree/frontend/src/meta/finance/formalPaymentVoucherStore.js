import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  getPaymentVoucherReviewById,
  listPaymentVoucherReviews,
  markPaymentVoucherReviewFormalVoucherCancelled,
  markPaymentVoucherReviewFormalVoucherGenerated,
} from './paymentVoucherReviewStore.js'

const STORAGE_KEY = 'formal-payment-voucher-state-v1'
const ACTIVE_STATUSES = ['generated']

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

function normalizePostingStatus(status) {
  const value = String(status || '').trim()
  if (['posted', '已过账'].includes(value)) return 'posted'
  if (['posting_ready', '可过账'].includes(value)) return 'posting_ready'
  if (['posting_blocked', '过账阻断'].includes(value)) return 'posting_blocked'
  return 'unposted'
}

function isUnpostedStatus(status) {
  return ['unposted', 'notPosted', 'not_posted', '未过账', 'posting_ready'].includes(String(status || '').trim())
}

function isPostedStatus(status) {
  return normalizePostingStatus(status) === 'posted'
}

function getPostingActionStatusText(status) {
  return {
    none: '未模拟',
    simulated: '已模拟过账',
    blocked: '模拟过账阻断',
  }[status] || '未模拟'
}

function isPostingSimulationCompleted(voucher = {}) {
  const actionStatus = String(voucher.postingActionStatus || '').trim()
  const actionText = String(voucher.postingActionStatusText || '').trim()
  return actionStatus === 'simulated'
    || voucher.postingSimulated === true
    || actionText === '已模拟过账'
    || actionText.includes('已模拟过账')
}

function defaultState() {
  return { formalPaymentVouchers: [] }
}

function getFormalPostingStatusText(status) {
  return {
    not_started: '未正式过账',
    ready: '可正式过账',
    blocked: '正式过账阻断',
    posted: '已正式过账',
  }[status] || '未正式过账'
}

function normalizeLine(line = {}, index = 0, source = {}) {
  return {
    id: line.id || createId('fpvl'),
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

function normalizeVoucher(item = {}) {
  const lines = Array.isArray(item.lines) ? item.lines.map((line, index) => normalizeLine(line, index, item)) : []
  const debitAmount = toSafeAmount(item.debitAmount ?? lines.filter((line) => line.direction === 'debit').reduce((sum, line) => sum + toSafeAmount(line.amount), 0))
  const creditAmount = toSafeAmount(item.creditAmount ?? lines.filter((line) => line.direction === 'credit').reduce((sum, line) => sum + toSafeAmount(line.amount), 0))
  const base = {
    id: item.id || createId('fpv'),
    formalVoucherNo: item.formalVoucherNo || createNo('FPV'),
    sourceVoucherReviewId: item.sourceVoucherReviewId || '',
    sourceVoucherReviewNo: item.sourceVoucherReviewNo || '',
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
    paymentDate: item.paymentDate || item.voucherDate || '',
    paymentMethod: item.paymentMethod || '',
    offlinePaymentRecordNo: item.offlinePaymentRecordNo || '',
    accountingPeriod: item.accountingPeriod || '',
    debitAmount,
    creditAmount,
    differenceAmount: toSafeAmount(item.differenceAmount ?? debitAmount - creditAmount),
    totalVoucherAmount: toSafeAmount(item.totalVoucherAmount ?? Math.max(debitAmount, creditAmount)),
    formalVoucherStatus: item.formalVoucherStatus || 'generated',
    postingStatus: normalizePostingStatus(item.postingStatus || 'unposted'),
    ledgerStatus: item.ledgerStatus || 'notWritten',
    paymentWriteOffStatus: item.paymentWriteOffStatus || 'notWrittenOff',
    postingActionStatus: item.postingActionStatus || 'none',
    postingActionStatusText: item.postingActionStatusText || getPostingActionStatusText(item.postingActionStatus || 'none'),
    postingSimulated: Boolean(item.postingSimulated),
    postingSimulatedAt: item.postingSimulatedAt || '',
    postingSimulatedBy: item.postingSimulatedBy || '',
    postingActionLogs: Array.isArray(item.postingActionLogs) ? item.postingActionLogs : [],
    postingActionConclusion: item.postingActionConclusion || '未执行模拟过账；本记录仍未正式过账、未写总账、未核销、未生成银行流水。',
    formalPostingStatus: item.formalPostingStatus || 'not_started',
    formalPostingStatusText: item.formalPostingStatusText || getFormalPostingStatusText(item.formalPostingStatus || 'not_started'),
    formalPostingReady: Boolean(item.formalPostingReady),
    formalPostingBlocked: Boolean(item.formalPostingBlocked),
    formalPostingBlockedReasons: Array.isArray(item.formalPostingBlockedReasons) ? item.formalPostingBlockedReasons : [],
    formalPostingWarnings: Array.isArray(item.formalPostingWarnings) ? item.formalPostingWarnings : [],
    formalPostingReviewConclusion: item.formalPostingReviewConclusion || '正式过账前最终设计评审待生成；本轮不执行正式过账、不写总账、不核销、不生成银行流水。',
    formalPostingLogs: Array.isArray(item.formalPostingLogs) ? item.formalPostingLogs : [],
    formalPostedAt: item.formalPostedAt || '',
    formalPostedBy: item.formalPostedBy || '',
    ledgerEntryId: item.ledgerEntryId || '',
    ledgerEntryNo: item.ledgerEntryNo || '',
    generatedBy: item.generatedBy || '当前凭证制单人',
    generatedAt: item.generatedAt || nowText(),
    cancelledBy: item.cancelledBy || '',
    cancelledAt: item.cancelledAt || '',
    riskLevel: item.riskLevel || 'pending',
    riskStatus: item.riskStatus || 'pending',
    riskItems: Array.isArray(item.riskItems) ? item.riskItems : [],
    lines,
    operationLogs: Array.isArray(item.operationLogs) ? item.operationLogs : [],
    createdAt: item.createdAt || nowText(),
    updatedAt: item.updatedAt || nowText(),
  }
  const postingPreReview = buildPostingPreReviewSummary(base)
  const postingReadiness = buildVoucherPostingReadinessSummary({ ...base, ...postingPreReview })
  const formalPostingReview = buildFormalPostingFinalReviewSummary({ ...base, ...postingPreReview, ...postingReadiness })
  return { ...base, ...postingPreReview, ...postingReadiness, ...formalPostingReview }
}

function normalizeState(raw = {}) {
  return {
    formalPaymentVouchers: (raw.formalPaymentVouchers || []).map(normalizeVoucher),
  }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[FORMAL PAYMENT VOUCHER STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function byId(id) {
  return state.formalPaymentVouchers.find((item) => String(item.id) === String(id)) || null
}

function activeByVoucherReviewId(voucherReviewId) {
  return state.formalPaymentVouchers.find((item) => (
    String(item.sourceVoucherReviewId) === String(voucherReviewId)
    && ACTIVE_STATUSES.includes(item.formalVoucherStatus)
  )) || null
}

export function writeFormalPaymentVoucherLog(action, payload = {}) {
  addOperationLog({
    module: '正式付款凭证',
    action,
    targetType: payload.targetType || 'formalPaymentVoucher',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源单据：${payload.sourceNo || '-'}`,
      `目标单据：${payload.targetNo || '-'}`,
      `结果：${payload.result || '成功'}`,
      '边界：本动作只生成正式付款凭证对象，不执行过账，不写总账，不做付款核销，不生成银行流水。',
    ].join('；'),
  })
}

export function getFormalPaymentVoucherState() {
  return clone(state)
}

export function saveFormalPaymentVoucherState(nextState = {}) {
  state = normalizeState(nextState)
  persist()
  return getFormalPaymentVoucherState()
}

export function resetFormalPaymentVoucherState() {
  state = defaultState()
  persist()
  return getFormalPaymentVoucherState()
}

export function listFormalPaymentVouchers() {
  return clone(state.formalPaymentVouchers)
}

export function getFormalPaymentVoucherById(id) {
  const item = byId(id)
  return item ? clone(item) : null
}

export function isFormalVoucherGenerated(voucherReviewId) {
  const existing = activeByVoucherReviewId(voucherReviewId)
  return existing ? clone(existing) : null
}

export function validateFormalVoucherSourceRisk(review = {}) {
  if (review.voucherReviewStatus !== 'passed' || review.voucherReviewResult !== 'passed') {
    return { result: 'blocked', level: 'blocked', message: '只有付款凭证复核通过的记录可以生成正式付款凭证。' }
  }
  const required = [
    review.sourceVoucherDraftNo,
    review.sourcePaymentRecordReviewNo,
    review.sourcePaymentExecutionNo,
    review.sourceRiskReviewNo || review.sourcePaymentOrderDraftNo,
    review.sourceApDraftNo || review.sourcePayablePrepareNo,
    review.sourcePurchaseOrderNo || review.rootRequestNo,
  ]
  if (required.some((value) => !hasText(value))) {
    return { result: 'blocked', level: 'blocked', message: '来源链缺失，请检查付款凭证复核、凭证草稿、付款执行、应付来源和采购来源。' }
  }
  return { result: 'passed', level: 'info', message: '来源复核和来源链检查通过。' }
}

export function validateFormalVoucherBalance(review = {}) {
  const debitCents = Math.round(toSafeAmount(review.debitAmount) * 100)
  const creditCents = Math.round(toSafeAmount(review.creditAmount) * 100)
  const diffCents = Math.round(toSafeAmount(review.differenceAmount) * 100)
  if (debitCents <= 0 || creditCents <= 0) {
    return { result: 'blocked', level: 'blocked', message: '借方金额和贷方金额必须大于 0。' }
  }
  if (debitCents !== creditCents || diffCents !== 0) {
    return { result: 'blocked', level: 'blocked', message: '借贷金额不平衡，不能生成正式付款凭证。' }
  }
  return { result: 'passed', level: 'info', message: '借贷金额平衡，差异金额为 0。' }
}

export function validateFormalVoucherAccounts(review = {}) {
  const lines = review.lines || []
  if (!lines.length) return { result: 'blocked', level: 'blocked', message: '凭证分录缺失，不能生成正式付款凭证。' }
  const missing = lines.some((line) => !hasText(line.accountCode) || !hasText(line.accountName))
  if (missing) return { result: 'blocked', level: 'blocked', message: '借方或贷方科目缺失，不能生成正式付款凭证。' }
  return { result: 'warning', level: 'warning', message: '当前科目为占位科目，可生成正式凭证对象，但后续过账前必须接入正式科目体系。' }
}

export function validateFormalVoucherPeriod(review = {}) {
  if (!hasText(review.voucherDate) || !hasText(review.accountingPeriod)) {
    return { result: 'warning', level: 'warning', message: '凭证日期或会计期间缺失，后续需接入正式会计期间管理。' }
  }
  return { result: 'passed', level: 'info', message: '凭证日期和会计期间已填写；本轮不实现期间关账。' }
}

export function validateFormalVoucherPostingBoundary(review = {}) {
  if (isPostedStatus(review.postingStatus) || review.ledgerStatus === 'written') {
    return { result: 'blocked', level: 'blocked', message: '来源已过账或已写总账，不能生成正式付款凭证。' }
  }
  if (!['notPosted', 'notWritten'].includes(review.ledgerStatus)) {
    return { result: 'blocked', level: 'blocked', message: '来源总账状态必须为未过账。' }
  }
  return { result: 'passed', level: 'info', message: '正式凭证生成不执行过账，生成后状态为未过账。' }
}

export function validateFormalVoucherLedgerBoundary() {
  return { result: 'passed', level: 'info', message: '正式凭证生成不写总账，生成后总账状态为未写总账。' }
}

function validateFormalVoucherWriteOffBoundary() {
  return { result: 'passed', level: 'info', message: '正式凭证生成不做付款核销，生成后核销状态为未核销。' }
}

function validateFormalVoucherDuplicate(review = {}) {
  const existing = activeByVoucherReviewId(review.id)
  if (existing) return { result: 'blocked', level: 'blocked', message: '该付款凭证复核已生成正式付款凭证，不能重复生成。' }
  return { result: 'passed', level: 'info', message: '未发现重复未关闭正式付款凭证。' }
}

export function buildPostingPreReviewSummary(voucher = {}) {
  const debitCents = Math.round(toSafeAmount(voucher.debitAmount) * 100)
  const creditCents = Math.round(toSafeAmount(voucher.creditAmount) * 100)
  const diffCents = Math.round(toSafeAmount(voucher.differenceAmount) * 100)
  const lines = Array.isArray(voucher.lines) ? voucher.lines : []
  const hasAccounts = lines.length && lines.every((line) => hasText(line.accountCode) && hasText(line.accountName))
  const hasBlockedRisk = (voucher.riskItems || []).some((item) => item.level === 'blocked' || item.result === 'blocked')
  const add = (itemCode, itemName, ok, failLevel, failMessage, passMessage) => ({
    itemCode,
    itemName,
    result: ok ? 'passed' : failLevel,
    level: ok ? 'info' : failLevel,
    message: ok ? passMessage : failMessage,
  })
  const items = [
    add('formalVoucherExists', '正式付款凭证存在检查', hasText(voucher.id) && hasText(voucher.formalVoucherNo), 'blocked', '正式付款凭证或凭证号缺失，不能进入过账阶段。', '正式付款凭证和凭证号已存在。'),
    add('formalVoucherStatus', '正式凭证状态检查', voucher.formalVoucherStatus === 'generated', 'blocked', '正式凭证状态不是“正式凭证已生成”，不能进入过账阶段。', '正式凭证状态为“正式凭证已生成”。'),
    add('postingStatus', '过账状态检查', isUnpostedStatus(voucher.postingStatus), 'blocked', '当前记录不是未过账状态，不能进入过账阶段。', '过账状态为未过账。'),
    add('ledgerStatus', '总账状态检查', voucher.ledgerStatus === 'notWritten', 'blocked', '当前记录不是未写总账状态，不能进入过账阶段。', '总账状态为未写总账。'),
    add('writeOffStatus', '核销状态检查', voucher.paymentWriteOffStatus === 'notWrittenOff', 'blocked', '当前记录不是未核销状态，不能进入过账阶段。', '核销状态为未核销。'),
    add('sourceVoucher', '来源付款凭证检查', hasText(voucher.sourceVoucherReviewNo) && hasText(voucher.sourceVoucherDraftNo), 'blocked', '来源付款凭证复核或付款凭证草稿缺失。', '来源付款凭证复核和付款凭证草稿已关联。'),
    add('paymentExecutionChain', '付款记录/执行链检查', hasText(voucher.sourcePaymentRecordReviewNo) && hasText(voucher.sourcePaymentExecutionNo), 'blocked', '来源付款记录复核或付款执行草稿缺失。', '来源付款记录复核和付款执行草稿已关联。'),
    add('purchaseSourceChain', '采购来源链检查', hasText(voucher.rootRequestNo) || hasText(voucher.sourcePurchaseOrderNo), 'blocked', '原始请购单和采购订单来源均缺失。', '已保留原始请购单或采购订单来源。'),
    add('amountValid', '金额有效性检查', debitCents > 0 && creditCents > 0 && debitCents === creditCents && diffCents === 0, 'blocked', '借贷金额必须大于 0、借贷平衡且差异为 0。', '金额有效，借贷平衡。'),
    add('paymentObject', '付款对象检查', hasText(voucher.supplierName) || hasText(voucher.supplierId), 'blocked', '付款对象缺失，不能进入过账阶段。', '付款对象已存在。'),
    add('paymentMethod', '付款方式检查', hasText(voucher.paymentMethod), 'warning', '付款方式缺失，后续过账前需补齐。', '付款方式已存在。'),
    add('paymentDate', '付款日期检查', hasText(voucher.paymentDate) || hasText(voucher.voucherDate), 'warning', '付款日期缺失，后续过账前需补齐。', '付款日期或凭证日期已存在。'),
    add('voucherNo', '凭证号检查', hasText(voucher.formalVoucherNo), 'blocked', '正式付款凭证号缺失。', '正式付款凭证号已存在。'),
    add('accountingPeriod', '会计期间检查', hasText(voucher.accountingPeriod), 'warning', '会计期间为占位或缺失，后续需接入正式会计期间。', '会计期间字段已具备。'),
    add('accountLines', '借贷科目检查', hasAccounts, 'warning', '借贷科目字段缺失或仍需接入正式科目体系。', '借贷科目字段已具备。'),
    add('blockingRisk', '不允许过账风险项检查', !hasBlockedRisk, 'blocked', '存在阻断风险项，不能进入过账阶段。', '未发现不允许过账的阻断风险项。'),
  ]
  const blockedCount = items.filter((item) => item.level === 'blocked').length
  const warningCount = items.filter((item) => item.level === 'warning').length
  const passedCount = items.filter((item) => item.result === 'passed').length
  return {
    postingPreReviewStatus: blockedCount ? 'blocked' : 'passed',
    postingPreReviewResult: blockedCount ? 'blocked' : (warningCount ? 'passedWithWarning' : 'passed'),
    postingPreReviewItems: items,
    postingPreReviewRiskCount: items.length,
    postingPreReviewBlockedCount: blockedCount,
    postingPreReviewWarningCount: warningCount,
    postingPreReviewPassedCount: passedCount,
    postingPreReviewCanEnterPosting: blockedCount === 0,
    postingPreReviewConclusion: blockedCount
      ? `存在 ${blockedCount} 个阻断项，不能进入后续过账阶段。`
      : (warningCount ? `过账前评审通过，有 ${warningCount} 个提醒项；可进入后续过账阶段，但本轮不执行真实过账。` : '过账前评审通过；可进入后续过账阶段，但本轮不执行真实过账。'),
    postingPreReviewUpdatedAt: nowText(),
  }
}

export function buildVoucherPostingReadinessSummary(voucher = {}) {
  const preReview = Array.isArray(voucher.postingPreReviewItems)
    ? voucher
    : { ...voucher, ...buildPostingPreReviewSummary(voucher) }
  const addBlock = (condition, message) => (condition ? [message] : [])
  const addWarning = (condition, message) => (condition ? [message] : [])
  const blockedReasons = [
    ...addBlock(!hasText(preReview.id) || !hasText(preReview.formalVoucherNo), '正式付款凭证或凭证号缺失。'),
    ...addBlock(preReview.formalVoucherStatus !== 'generated', '正式凭证状态不是“正式凭证已生成”。'),
    ...addBlock(preReview.postingPreReviewStatus !== 'passed', '过账前评审未通过。'),
    ...addBlock(Number(preReview.postingPreReviewBlockedCount || 0) > 0, `过账前评审仍有 ${preReview.postingPreReviewBlockedCount || 0} 个阻断项。`),
    ...addBlock(!isUnpostedStatus(preReview.postingStatus), '当前记录不是未过账状态。'),
    ...addBlock(preReview.ledgerStatus !== 'notWritten', '当前记录不是未写总账状态。'),
    ...addBlock(preReview.paymentWriteOffStatus !== 'notWrittenOff', '当前记录不是未核销状态。'),
    ...addBlock(toSafeAmount(preReview.debitAmount) <= 0 || toSafeAmount(preReview.creditAmount) <= 0, '借方金额和贷方金额必须大于 0。'),
    ...addBlock(Math.round(toSafeAmount(preReview.debitAmount) * 100) !== Math.round(toSafeAmount(preReview.creditAmount) * 100), '借贷金额必须一致。'),
    ...addBlock(Math.round(toSafeAmount(preReview.differenceAmount) * 100) !== 0, '差异金额必须为 0。'),
    ...addBlock(!hasText(preReview.supplierName) && !hasText(preReview.supplierId), '付款对象缺失。'),
    ...addBlock(!hasText(preReview.sourceVoucherReviewNo) || !hasText(preReview.sourceVoucherDraftNo), '来源付款凭证复核或付款凭证草稿缺失。'),
    ...addBlock(!hasText(preReview.sourcePaymentRecordReviewNo) || !hasText(preReview.sourcePaymentExecutionNo), '来源付款记录复核或付款执行链缺失。'),
    ...addBlock(!hasText(preReview.rootRequestNo) && !hasText(preReview.sourcePurchaseOrderNo), '原始请购单和采购订单来源均缺失。'),
  ]
  const warnings = [
    ...addWarning(!hasText(preReview.paymentDate) && !hasText(preReview.voucherDate), '付款日期缺失，后续正式过账前需补齐。'),
    ...addWarning(!hasText(preReview.paymentMethod), '付款方式缺失，后续正式过账前需补齐。'),
    ...addWarning(!hasText(preReview.accountingPeriod), '会计期间缺失，后续正式过账前需接入正式期间。'),
    ...addWarning(!Array.isArray(preReview.lines) || !preReview.lines.length, '借贷分录缺失，后续正式过账前需补齐。'),
  ]
  const postingReady = blockedReasons.length === 0
  return {
    postingStatus: postingReady ? 'posting_ready' : (isPostedStatus(preReview.postingStatus) ? 'posted' : 'posting_blocked'),
    postingStatusText: postingReady ? '可过账' : (isPostedStatus(preReview.postingStatus) ? '已过账' : '过账阻断'),
    postingReady,
    postingBlocked: !postingReady,
    postingBlockedReasons: blockedReasons,
    postingWarnings: warnings,
    postingBlockedCount: blockedReasons.length,
    postingWarningCount: warnings.length,
    postingReadinessStatus: postingReady ? 'ready' : 'blocked',
    postingReadinessConclusion: postingReady
      ? (warnings.length ? `可进入凭证过账，有 ${warnings.length} 个提醒项；本轮不写总账、不核销、不生成银行流水。` : '可进入凭证过账；本轮不写总账、不核销、不生成银行流水。')
      : `存在 ${blockedReasons.length} 个过账阻断原因，不可过账。`,
    postedAt: preReview.postedAt || '',
    postedBy: preReview.postedBy || '',
  }
}

export function buildFormalPostingFinalReviewSummary(voucher = {}) {
  const reviewed = Array.isArray(voucher.postingPreReviewItems)
    ? voucher
    : { ...voucher, ...buildPostingPreReviewSummary(voucher) }
  const readyView = typeof reviewed.postingReady === 'boolean'
    ? reviewed
    : { ...reviewed, ...buildVoucherPostingReadinessSummary(reviewed) }
  const addBlock = (condition, message) => (condition ? [message] : [])
  const addWarning = (condition, message) => (condition ? [message] : [])
  const amountInvalid = toSafeAmount(readyView.debitAmount) <= 0
    || toSafeAmount(readyView.creditAmount) <= 0
    || Math.round(toSafeAmount(readyView.debitAmount) * 100) !== Math.round(toSafeAmount(readyView.creditAmount) * 100)
    || Math.round(toSafeAmount(readyView.differenceAmount) * 100) !== 0
  const bankFlowExists = Boolean(
    readyView.bankFlowGenerated
    || readyView.bankFlowNo
    || readyView.bankTransactionNo
    || readyView.bankStatementNo
  )
  const blocks = [
    ...addBlock(!hasText(readyView.id) || !hasText(readyView.formalVoucherNo), '正式付款凭证或凭证号缺失。'),
    ...addBlock(readyView.formalVoucherStatus !== 'generated', '正式付款凭证状态不是“正式凭证已生成”。'),
    ...addBlock(readyView.postingStatus !== 'posting_ready', '凭证过账准备状态不是“可过账”。'),
    ...addBlock(readyView.postingReady !== true, '凭证过账准备结果不是可过账。'),
    ...addBlock(readyView.postingBlocked === true, '凭证过账准备仍存在阻断。'),
    ...addBlock(readyView.postingPreReviewStatus !== 'passed', '过账前评审未通过。'),
    ...addBlock(Number(readyView.postingPreReviewBlockedCount || 0) > 0, `过账前评审仍有 ${readyView.postingPreReviewBlockedCount || 0} 个阻断项。`),
    ...addBlock(!isPostingSimulationCompleted(readyView), '模拟过账尚未完成；正式过账前必须先完成模拟过账。'),
    ...addBlock(readyView.ledgerStatus !== 'notWritten', '总账状态不是“未写总账”。'),
    ...addBlock(readyView.paymentWriteOffStatus !== 'notWrittenOff', '核销状态不是“未核销”。'),
    ...addBlock(bankFlowExists, '已存在银行流水信息，不允许进入本轮正式过账设计口径。'),
    ...addBlock(amountInvalid, '金额无效；借贷金额必须大于 0、借贷平衡且差异为 0。'),
    ...addBlock(!hasText(readyView.sourceVoucherReviewNo) || !hasText(readyView.sourceVoucherDraftNo), '来源付款凭证复核或付款凭证草稿缺失。'),
    ...addBlock(!hasText(readyView.sourcePaymentRecordReviewNo) || !hasText(readyView.sourcePaymentExecutionNo), '来源付款记录复核或付款执行链缺失。'),
    ...addBlock(!hasText(readyView.rootRequestNo) && !hasText(readyView.sourcePurchaseOrderNo), '原始请购单和采购订单来源均缺失。'),
    ...addBlock(!hasText(readyView.supplierName) && !hasText(readyView.supplierId), '付款对象缺失。'),
    ...addBlock(hasText(readyView.ledgerEntryId) || hasText(readyView.ledgerEntryNo), '已存在总账凭证编号或总账凭证 ID，不能重复进入正式过账。'),
    ...addBlock(hasText(readyView.formalPostedAt) || hasText(readyView.formalPostedBy), '已存在正式过账时间或正式过账人，不能重复进入正式过账。'),
  ]
  const warnings = [
    ...addWarning(!hasText(readyView.paymentDate) && !hasText(readyView.voucherDate), '付款日期缺失；正式过账前需补齐或接入正式日期规则。'),
    ...addWarning(!hasText(readyView.paymentMethod), '付款方式缺失；正式过账前需补齐或接入正式付款方式规则。'),
    ...addWarning(!hasText(readyView.accountingPeriod), '会计期间为空；正式过账前需接入正式期间管理和关账检查。'),
    ...addWarning(!Array.isArray(readyView.lines) || !readyView.lines.length, '借贷分录为空；正式过账前需确认正式科目体系。'),
    '正式科目体系、会计期间锁定、过账权限、审计审批仍为后续阶段能力，本轮仅做设计评审。',
  ]
  const isReady = blocks.length === 0
  const formalPostingStatus = isReady ? 'ready' : 'blocked'
  return {
    formalPostingStatus,
    formalPostingStatusText: getFormalPostingStatusText(formalPostingStatus),
    formalPostingReady: isReady,
    formalPostingBlocked: !isReady,
    formalPostingBlockedReasons: blocks,
    formalPostingWarnings: warnings,
    formalPostingBlockedCount: blocks.length,
    formalPostingWarningCount: warnings.length,
    formalPostingReviewConclusion: isReady
      ? `正式过账前最终设计评审通过；当前仅表示未来可进入正式过账设计阶段，本轮不正式过账、不写总账、不核销、不生成银行流水。提醒项 ${warnings.length} 个。`
      : `正式过账前最终设计评审阻断：存在 ${blocks.length} 个阻断项。本轮不正式过账、不写总账、不核销、不生成银行流水。`,
    formalPostingDesignFields: [
      'formalPostingStatus',
      'formalPostingReady',
      'formalPostingBlocked',
      'formalPostingBlockedReasons',
      'formalPostingWarnings',
      'formalPostedAt',
      'formalPostedBy',
      'ledgerEntryId',
      'ledgerEntryNo',
    ],
    formalPostingLogTemplate: {
      actionType: '正式过账',
      designOnly: true,
      ledgerWritten: false,
      writeOffCompleted: false,
      bankFlowGenerated: false,
      remark: '本轮仅定义未来正式过账日志结构，不写入真实正式过账日志。',
    },
  }
}

export function buildFormalVoucherRiskItems(review = {}) {
  const sourceCheck = validateFormalVoucherSourceRisk(review)
  const balanceCheck = validateFormalVoucherBalance(review)
  const accountCheck = validateFormalVoucherAccounts(review)
  const periodCheck = validateFormalVoucherPeriod(review)
  const postingCheck = validateFormalVoucherPostingBoundary(review)
  const ledgerCheck = validateFormalVoucherLedgerBoundary(review)
  const duplicateCheck = validateFormalVoucherDuplicate(review)
  const writeOffCheck = validateFormalVoucherWriteOffBoundary(review)
  const amount = Math.round(Math.max(toSafeAmount(review.debitAmount), toSafeAmount(review.creditAmount)) * 100)
  const items = [
    { itemCode: 'sourceReview', itemName: '来源复核检查', ...sourceCheck },
    { itemCode: 'sourceChain', itemName: '来源链完整性检查', ...sourceCheck },
    { itemCode: 'balance', itemName: '借贷平衡检查', ...balanceCheck },
    {
      itemCode: 'amount',
      itemName: '金额一致性检查',
      result: amount > 0 ? 'passed' : 'blocked',
      level: amount > 0 ? 'info' : 'blocked',
      message: amount > 0 ? '金额检查通过，按两位小数处理。' : '正式凭证金额必须大于 0。',
    },
    { itemCode: 'account', itemName: '科目检查', ...accountCheck },
    { itemCode: 'period', itemName: '会计期间检查', ...periodCheck },
    { itemCode: 'duplicate', itemName: '防重复正式凭证检查', ...duplicateCheck },
    {
      itemCode: 'permission',
      itemName: '权限边界检查',
      result: 'warning',
      level: 'warning',
      message: '当前使用本地演示制单人，后续需接入正式登录用户、岗位权限和审批流。',
    },
    {
      itemCode: 'audit',
      itemName: '审计检查',
      result: 'passed',
      level: 'info',
      message: '正式凭证对象将保存来源链、生成时间、生成操作人和风险评审结果。',
    },
    { itemCode: 'postingBoundary', itemName: '过账边界检查', ...postingCheck },
    { itemCode: 'ledgerBoundary', itemName: '总账边界检查', ...ledgerCheck },
    { itemCode: 'writeOffBoundary', itemName: '核销边界检查', ...writeOffCheck },
  ]
  const hasBlocked = items.some((item) => item.level === 'blocked')
  const hasWarning = items.some((item) => item.level === 'warning')
  return {
    riskItems: items,
    riskStatus: hasBlocked ? 'blocked' : (hasWarning ? 'warning' : 'passed'),
    riskLevel: hasBlocked ? 'blocked' : (hasWarning ? 'warning' : 'low'),
  }
}

export function validateFormalVoucherSource(review = {}) {
  if (!review?.id) return '未找到付款凭证复核。'
  if (review.voucherReviewStatus !== 'passed' || review.voucherReviewResult !== 'passed') return '只有付款凭证复核通过的记录可以生成正式付款凭证。'
  if (!hasText(review.sourceVoucherDraftNo)) return '来源付款凭证草稿缺失，不能生成正式付款凭证。'
  if (toSafeAmount(review.debitAmount) <= 0 || toSafeAmount(review.creditAmount) <= 0) return '借方金额和贷方金额必须大于 0。'
  if (Math.round(toSafeAmount(review.debitAmount) * 100) !== Math.round(toSafeAmount(review.creditAmount) * 100)) return '借贷金额不平衡，不能生成正式付款凭证。'
  if (Math.round(toSafeAmount(review.differenceAmount) * 100) !== 0) return '差异金额必须为 0。'
  if (!['notPosted', 'notWritten'].includes(review.ledgerStatus)) return '来源总账状态必须为未过账或未写总账。'
  if (activeByVoucherReviewId(review.id)) return '该付款凭证复核已生成正式付款凭证，不能重复生成。'
  const risk = buildFormalVoucherRiskItems(review)
  if (risk.riskStatus === 'blocked') {
    const blocked = risk.riskItems.find((item) => item.level === 'blocked')
    return blocked?.message || '存在阻断风险，不能生成正式付款凭证。'
  }
  return ''
}

export function getFormalVoucherSourcesFromVoucherReviews() {
  return listPaymentVoucherReviews().map((review) => {
    const existing = activeByVoucherReviewId(review.id)
    const disabledReason = existing ? '该付款凭证复核已生成正式付款凭证，不能重复生成。' : validateFormalVoucherSource(review)
    return {
      ...review,
      formalVoucherGenerated: Boolean(existing),
      targetFormalVoucherId: existing?.id || '',
      targetFormalVoucherNo: existing?.formalVoucherNo || '',
      canGenerateFormalVoucher: !disabledReason,
      disabledReason,
    }
  })
}

function buildFormalVoucherFromReview(review = {}) {
  const formalVoucher = normalizeVoucher({
    sourceVoucherReviewId: review.id,
    sourceVoucherReviewNo: review.voucherReviewNo,
    sourceVoucherDraftId: review.sourceVoucherDraftId,
    sourceVoucherDraftNo: review.sourceVoucherDraftNo,
    sourcePaymentRecordReviewNo: review.sourcePaymentRecordReviewNo,
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
    voucherDate: review.voucherDate,
    accountingPeriod: review.accountingPeriod,
    debitAmount: review.debitAmount,
    creditAmount: review.creditAmount,
    differenceAmount: review.differenceAmount,
    totalVoucherAmount: Math.max(toSafeAmount(review.debitAmount), toSafeAmount(review.creditAmount)),
    formalVoucherStatus: 'generated',
    postingStatus: 'unposted',
    ledgerStatus: 'notWritten',
    paymentWriteOffStatus: 'notWrittenOff',
    generatedBy: '当前凭证制单人',
    generatedAt: nowText(),
    lines: review.lines || [],
  })
  const risk = buildFormalVoucherRiskItems(review)
  return normalizeVoucher({ ...formalVoucher, ...risk })
}

export function createFormalVoucherFromVoucherReview(voucherReviewId) {
  const review = getPaymentVoucherReviewById(voucherReviewId)
  if (!review) return { success: false, error: '未找到付款凭证复核。' }
  const existing = activeByVoucherReviewId(review.id)
  if (existing) {
    writeFormalPaymentVoucherLog('防重复生成正式付款凭证', {
      sourceNo: review.voucherReviewNo,
      targetId: existing.id,
      targetNo: existing.formalVoucherNo,
      result: '已存在未关闭正式付款凭证，无需重复生成。',
    })
    return {
      success: true,
      alreadyDone: true,
      formalVoucher: clone(existing),
      message: '该付款凭证复核已生成正式付款凭证，不能重复生成。',
    }
  }
  const disabledReason = validateFormalVoucherSource(review)
  if (disabledReason) return { success: false, error: disabledReason }
  const formalVoucher = buildFormalVoucherFromReview(review)
  state.formalPaymentVouchers.unshift(formalVoucher)
  persist()
  markPaymentVoucherReviewFormalVoucherGenerated(review.id, formalVoucher)
  writeFormalPaymentVoucherLog('生成正式付款凭证', {
    sourceNo: review.voucherReviewNo,
    targetId: formalVoucher.id,
    targetNo: formalVoucher.formalVoucherNo,
    result: '已生成正式付款凭证对象；未过账、未写总账、未核销。',
  })
  return { success: true, formalVoucher: clone(formalVoucher) }
}

export function cancelFormalVoucher(id) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到正式付款凭证。' }
  if (current.formalVoucherStatus === 'cancelled') return { success: true, alreadyDone: true, formalVoucher: clone(current), message: '该正式付款凭证已取消，无需重复取消。' }
  if (!isUnpostedStatus(current.postingStatus) || current.ledgerStatus !== 'notWritten' || current.paymentWriteOffStatus !== 'notWrittenOff') return { success: false, error: '已过账、已写总账或已核销的凭证不能取消。' }
  Object.assign(current, {
    formalVoucherStatus: 'cancelled',
    cancelledBy: '当前凭证制单人',
    cancelledAt: nowText(),
    updatedAt: nowText(),
  })
  persist()
  markPaymentVoucherReviewFormalVoucherCancelled(current.sourceVoucherReviewId, current)
  writeFormalPaymentVoucherLog('取消正式付款凭证', {
    sourceNo: current.sourceVoucherReviewNo,
    targetId: current.id,
    targetNo: current.formalVoucherNo,
    result: '已取消正式付款凭证对象；未过账、未写总账、未核销。',
  })
  return { success: true, formalVoucher: clone(current) }
}

export function validatePostingSimulation(voucher = {}) {
  if (!voucher?.id) return ['未找到正式付款凭证。']
  if (isPostingSimulationCompleted(voucher)) return ['该正式付款凭证已模拟过账，不能重复模拟。']
  const normalized = normalizeVoucher(voucher)
  const reasons = [...(normalized.postingBlockedReasons || [])]
  if (normalized.formalVoucherStatus !== 'generated') reasons.push('正式凭证状态不是“正式凭证已生成”。')
  if (normalized.postingStatus !== 'posting_ready') reasons.push('当前凭证过账状态不是“可过账”。')
  if (!normalized.postingReady || normalized.postingBlocked) reasons.push('凭证过账准备状态未通过。')
  if (normalized.ledgerStatus !== 'notWritten') reasons.push('总账状态不是未写总账。')
  if (normalized.paymentWriteOffStatus !== 'notWrittenOff') reasons.push('核销状态不是未核销。')
  if (toSafeAmount(normalized.debitAmount) <= 0 || toSafeAmount(normalized.creditAmount) <= 0) reasons.push('金额必须大于 0。')
  if (!hasText(normalized.sourceVoucherReviewNo) || !hasText(normalized.sourceVoucherDraftNo)) reasons.push('来源付款凭证链缺失。')
  if (!hasText(normalized.sourcePaymentRecordReviewNo) || !hasText(normalized.sourcePaymentExecutionNo)) reasons.push('来源付款记录或付款执行链缺失。')
  return [...new Set(reasons)]
}

export function simulateFormalVoucherPosting(id) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到正式付款凭证。' }
  if (isPostingSimulationCompleted(current)) {
    return { success: true, alreadyDone: true, formalVoucher: clone(current), message: '该正式付款凭证已模拟过账，不能重复模拟。' }
  }
  const blockedReasons = validatePostingSimulation(current)
  const beforeStatus = current.postingStatus
  const log = {
    id: createId('posting-action-log'),
    actionType: '模拟过账',
    actionTime: nowText(),
    operator: 'system',
    formalVoucherNo: current.formalVoucherNo,
    amount: toSafeAmount(current.totalVoucherAmount || Math.max(current.debitAmount, current.creditAmount)),
    beforePostingStatus: beforeStatus,
    afterPostingActionStatus: blockedReasons.length ? 'blocked' : 'simulated',
    result: blockedReasons.length ? '模拟过账阻断' : '已模拟过账',
    blockedReasons,
    ledgerWritten: false,
    writeOffCompleted: false,
    bankFlowGenerated: false,
  }
  const nextLogs = [...(current.postingActionLogs || []), log]
  if (blockedReasons.length) {
    Object.assign(current, {
      postingActionStatus: 'blocked',
      postingActionStatusText: getPostingActionStatusText('blocked'),
      postingActionLogs: nextLogs,
      postingActionConclusion: `模拟过账阻断：${blockedReasons.join('；')}`,
      updatedAt: nowText(),
    })
    persist()
    return { success: false, error: '当前正式付款凭证不满足模拟过账条件。', formalVoucher: clone(current), blockedReasons }
  }
  Object.assign(current, {
    postingActionStatus: 'simulated',
    postingActionStatusText: getPostingActionStatusText('simulated'),
    postingSimulated: true,
    postingSimulatedAt: log.actionTime,
    postingSimulatedBy: log.operator,
    postingActionLogs: nextLogs,
    postingActionConclusion: '已完成模拟过账；本动作不写总账、不核销、不生成银行流水，不代表正式过账。',
    updatedAt: nowText(),
  })
  persist()
  writeFormalPaymentVoucherLog('模拟过账', {
    sourceNo: current.sourceVoucherReviewNo,
    targetId: current.id,
    targetNo: current.formalVoucherNo,
    result: '已模拟过账；未写总账、未核销、未生成银行流水。',
  })
  return { success: true, formalVoucher: clone(current), log }
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
    const formalVoucher = outcome.formalVoucher || {}
    if (outcome.alreadyDone) {
      result.alreadyDoneCount += 1
      result.alreadyDoneItems.push({ id, no, status: formalVoucher.formalVoucherStatus })
    } else {
      result.successCount += 1
      result.successItems.push({ id, no, status: formalVoucher.formalVoucherStatus })
    }
  })
  result.nextSuggestion = result.failedCount
    ? '请按失败原因处理后再重试；本批量动作不会过账、不会写总账、不会核销。'
    : '本批量动作已完成或已达成；正式凭证对象仍处于未过账、未写总账、未核销状态。'
  writeFormalPaymentVoucherLog(label, {
    targetType: 'batchFormalPaymentVoucher',
    targetId: label,
    result: `成功 ${result.successCount} 条，已达成 ${result.alreadyDoneCount} 条，失败 ${result.failedCount} 条。`,
  })
  return result
}

export function batchCreateFormalVouchersFromVoucherReviews(ids = []) {
  return batchResult(ids, createFormalVoucherFromVoucherReview, '批量生成正式付款凭证', (id) => getPaymentVoucherReviewById(id)?.voucherReviewNo || id)
}

export function batchCancelFormalVouchers(ids = []) {
  return batchResult(ids, cancelFormalVoucher, '批量取消正式付款凭证', (id) => byId(id)?.formalVoucherNo || id)
}

export function getFormalVoucherStatusLabel(status) {
  return {
    generated: '正式凭证已生成',
    cancelled: '已取消',
  }[status] || status || '-'
}

export function getFormalVoucherStatusType(status) {
  return {
    generated: 'success',
    cancelled: 'info',
  }[status] || 'info'
}

export function getPostingStatusLabel(status) {
  return {
    unposted: '未过账',
    notPosted: '未过账',
    not_posted: '未过账',
    posting_ready: '可过账',
    postingReady: '可过账',
    posting_blocked: '过账阻断',
    posted: '已过账',
  }[status] || status || '-'
}

export function getLedgerStatusLabel(status) {
  return {
    notWritten: '未写总账',
  }[status] || status || '-'
}

export function getPaymentWriteOffStatusLabel(status) {
  return {
    notWrittenOff: '未核销',
  }[status] || status || '-'
}

export function getFormalVoucherRiskLevelLabel(level) {
  return {
    pending: '待检查',
    low: '低风险',
    warning: '有警告',
    blocked: '阻断',
  }[level] || level || '-'
}

export function getFormalVoucherRiskLevelType(level) {
  return {
    low: 'success',
    warning: 'warning',
    blocked: 'danger',
    pending: 'info',
  }[level] || 'info'
}
