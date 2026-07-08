import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  getPaymentOrderDraftById,
  listPaymentOrderDrafts,
} from './paymentOrderDraftStore.js'

const STORAGE_KEY = 'payment-execution-risk-review-state-v1'

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
  const next = Number(String(value ?? 0).replace(/,/g, ''))
  return Number.isFinite(next) ? next : 0
}

function roundAmount(value) {
  return Number(toNumber(value).toFixed(2))
}

function amountValuePresent(value) {
  return value !== null && value !== undefined && String(value).trim() !== ''
}

function normalizeAmountValue(value) {
  if (!amountValuePresent(value)) return { amount: 0, invalid: false, empty: true, raw: value }
  const normalized = Number(String(value).replace(/,/g, '').trim())
  if (!Number.isFinite(normalized)) return { amount: 0, invalid: true, empty: false, raw: value }
  return {
    amount: Math.round(normalized * 100) / 100,
    invalid: false,
    empty: false,
    raw: value,
    decimalOverflow: hasMoreThanTwoDecimals(value),
  }
}

function toSafeAmount(value) {
  return normalizeAmountValue(value).amount
}

function hasMoreThanTwoDecimals(value) {
  const text = String(value ?? '').replace(/,/g, '').trim()
  if (!text || !Number.isFinite(Number(text))) return false
  const [, decimals = ''] = text.split('.')
  return decimals.length > 2
}

function pickAmount(source = {}, fields = []) {
  for (const field of fields) {
    if (amountValuePresent(source[field])) {
      return { ...normalizeAmountValue(source[field]), field }
    }
  }
  return { amount: 0, invalid: false, empty: true, raw: '', field: fields[0] || '' }
}

function resolvePaymentRiskAmounts(draft = {}) {
  const pay = pickAmount(draft, [
    'confirmedPayAmount',
    'draftPayAmount',
    'preparePayAmount',
    'approvedPayAmount',
    'applyPayAmount',
    'totalPayableAmount',
  ])
  let unpaid = pickAmount(draft, ['unpaidAmount'])
  if (unpaid.empty) {
    const paidAmount = toSafeAmount(draft.paidAmount)
    const totalPayable = normalizeAmountValue(draft.totalPayableAmount)
    const totalInvoice = normalizeAmountValue(draft.totalInvoiceAmount)
    if (!totalPayable.empty) {
      unpaid = {
        amount: Math.round((totalPayable.amount - paidAmount) * 100) / 100,
        invalid: totalPayable.invalid,
        empty: false,
        raw: `${draft.totalPayableAmount || 0} - ${draft.paidAmount || 0}`,
        field: 'totalPayableAmount - paidAmount',
        decimalOverflow: totalPayable.decimalOverflow,
      }
    } else if (!totalInvoice.empty) {
      unpaid = {
        amount: Math.round((totalInvoice.amount - paidAmount) * 100) / 100,
        invalid: totalInvoice.invalid,
        empty: false,
        raw: `${draft.totalInvoiceAmount || 0} - ${draft.paidAmount || 0}`,
        field: 'totalInvoiceAmount - paidAmount',
        decimalOverflow: totalInvoice.decimalOverflow,
      }
    } else {
      unpaid = pickAmount(draft, ['totalPayableAmount'])
    }
  }
  return {
    payAmount: pay.amount,
    unpaidAmount: unpaid.amount,
    payAmountCents: Math.round(pay.amount * 100),
    unpaidAmountCents: Math.round(unpaid.amount * 100),
    payAmountField: pay.field,
    unpaidAmountField: unpaid.field,
    payAmountInvalid: pay.invalid,
    unpaidAmountInvalid: unpaid.invalid,
    payAmountEmpty: pay.empty,
    unpaidAmountEmpty: unpaid.empty,
    decimalOverflow: Boolean(pay.decimalOverflow || unpaid.decimalOverflow),
  }
}

function defaultRules() {
  return [
    { key: 'paymentOrderStatus', label: '付款单状态检查', severity: 'error' },
    { key: 'supplierBank', label: '供应商银行账户检查', severity: 'error' },
    { key: 'companyPaymentAccount', label: '企业付款账户检查', severity: 'error' },
    { key: 'amount', label: '金额检查', severity: 'error' },
    { key: 'sourceTrace', label: '发票与应付链路检查', severity: 'error' },
    { key: 'duplicatePayment', label: '防重复付款检查', severity: 'error' },
    { key: 'approval', label: '审批检查', severity: 'warning' },
    { key: 'financeBoundary', label: '财务边界检查', severity: 'info' },
    { key: 'mockBankInfo', label: '模拟银行信息检查', severity: 'error' },
  ]
}

function defaultState() {
  return {
    riskReviewRules: defaultRules(),
    reviewResults: [],
  }
}

function normalizeReviewResult(result = {}) {
  return {
    id: result.id || createId('per'),
    riskReviewNo: result.riskReviewNo || createNo('PER'),
    sourcePaymentOrderDraftId: result.sourcePaymentOrderDraftId || result.paymentOrderDraftId || '',
    sourcePaymentOrderDraftNo: result.sourcePaymentOrderDraftNo || result.paymentOrderDraftNo || '',
    sourcePaymentPrepareNo: result.sourcePaymentPrepareNo || '',
    sourcePaymentDraftNo: result.sourcePaymentDraftNo || '',
    sourceApDraftNo: result.sourceApDraftNo || '',
    sourceInvoicePrepareNo: result.sourceInvoicePrepareNo || '',
    sourcePayableCheckNo: result.sourcePayableCheckNo || '',
    sourcePayablePrepareNo: result.sourcePayablePrepareNo || '',
    sourcePurchaseOrderNo: result.sourcePurchaseOrderNo || '',
    sourceReceiveNo: result.sourceReceiveNo || '',
    sourceInspectionNo: result.sourceInspectionNo || '',
    sourceInventoryTransactionNos: Array.isArray(result.sourceInventoryTransactionNos) ? result.sourceInventoryTransactionNos : [],
    rootRequestNo: result.rootRequestNo || '',
    supplierId: result.supplierId || '',
    supplierName: result.supplierName || '',
    paymentAccount: result.paymentAccount || '',
    paymentAccountName: result.paymentAccountName || '',
    paymentBankName: result.paymentBankName || '',
    supplierBankName: result.supplierBankName || '',
    supplierBankAccount: result.supplierBankAccount || '',
    supplierBankAccountName: result.supplierBankAccountName || '',
    confirmedPayAmount: roundAmount(result.confirmedPayAmount),
    unpaidAmount: roundAmount(result.unpaidAmount),
    checkPayAmount: roundAmount(result.checkPayAmount ?? result.confirmedPayAmount),
    checkUnpaidAmount: roundAmount(result.checkUnpaidAmount ?? result.unpaidAmount),
    checkPayAmountField: result.checkPayAmountField || '',
    checkUnpaidAmountField: result.checkUnpaidAmountField || '',
    paymentOrderStatus: result.paymentOrderStatus || '',
    voucherStatus: result.voucherStatus || '',
    bankPaymentStatus: result.bankPaymentStatus || '',
    bankInfoMocked: Boolean(result.bankInfoMocked),
    paymentBankInfoMocked: Boolean(result.paymentBankInfoMocked),
    supplierBankInfoMocked: Boolean(result.supplierBankInfoMocked),
    bankInfoMockRemark: result.bankInfoMockRemark || '',
    riskReviewStatus: result.riskReviewStatus || 'pending',
    riskLevel: result.riskLevel || 'medium',
    blockingReasons: Array.isArray(result.blockingReasons) ? result.blockingReasons : [],
    warningReasons: Array.isArray(result.warningReasons) ? result.warningReasons : [],
    reviewItems: Array.isArray(result.reviewItems) ? result.reviewItems : [],
    nextSuggestion: result.nextSuggestion || '',
    reviewedAt: result.reviewedAt || '',
    reviewedBy: result.reviewedBy || '',
    cancelledAt: result.cancelledAt || '',
    createdAt: result.createdAt || nowText(),
    updatedAt: result.updatedAt || nowText(),
  }
}

function normalizeState(raw = {}) {
  return {
    riskReviewRules: Array.isArray(raw.riskReviewRules) && raw.riskReviewRules.length ? raw.riskReviewRules : defaultRules(),
    reviewResults: (raw.reviewResults || []).map(normalizeReviewResult),
  }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[PAYMENT RISK REVIEW STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function byId(collection, id) {
  return (collection || []).find((item) => String(item.id) === String(id)) || null
}

function byDraftId(draftId) {
  return state.reviewResults.find((item) => String(item.sourcePaymentOrderDraftId) === String(draftId)) || null
}

function writeRiskReviewLog(action, payload = {}) {
  addOperationLog({
    module: '真实付款风险评审',
    action,
    targetType: payload.targetType || 'paymentExecutionRiskReview',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源单据：${payload.sourceNo || '-'}`,
      `目标单据：${payload.targetNo || '-'}`,
      `结果：${payload.result || '成功'}`,
    ].join('；'),
  })
}

function sourceInventoryText(row = {}) {
  const nos = row.sourceInventoryTransactionNos || row.sourceInventoryTransactionNo || ''
  if (Array.isArray(nos)) return nos.filter(Boolean)
  return nos ? [nos] : []
}

function hasText(value) {
  return String(value || '').trim().length > 0
}

function looksMockAccount(value) {
  const text = String(value || '').toLowerCase()
  return text.includes('mock') || text.includes('demo') || text.includes('test') || text.includes('模拟') || text.includes('测试')
}

function hasMockBankInfo(draft = {}) {
  const remark = `${draft.bankInfoMockRemark || ''}${draft.paymentBankInfoMockRemark || ''}${draft.supplierBankInfoMockRemark || ''}`
  return Boolean(
    draft.bankInfoMocked
    || draft.paymentBankInfoMocked
    || draft.supplierBankInfoMocked
    || remark.includes('模拟')
    || looksMockAccount(draft.supplierBankAccount)
    || looksMockAccount(draft.paymentAccount)
  )
}

function hasDuplicatePaymentRisk(draft = {}) {
  return Boolean(
    draft.realPaymentDraftGenerated
    || draft.realPaymentNo
    || draft.paymentExecutionRecordNo
    || draft.paymentExecutionStatus === 'paid'
    || draft.bankPaymentStatus === 'paid'
    || draft.realPaymentStatus === 'paid'
    || (draft.actualPayDate && toNumber(draft.paidAmount) >= toNumber(draft.confirmedPayAmount))
  )
}

function buildReviewItem(key, label, passed, message, severity = 'error', suggestion = '请按阻断原因处理后重新评审。', extra = {}) {
  return {
    key,
    label,
    passed: Boolean(passed),
    result: passed ? 'passed' : (severity === 'warning' ? 'warning' : 'blocked'),
    severity: passed ? 'info' : severity,
    message: passed ? '检查通过。' : message,
    suggestion: passed ? '无需处理。' : suggestion,
    ...extra,
  }
}

function buildAmountReview(amounts = {}) {
  let passed = true
  let message = '金额检查通过。'
  if (amounts.payAmountInvalid || amounts.payAmountEmpty) {
    passed = false
    message = '确认付款金额缺失或无效，请检查付款金额字段。'
  } else if (amounts.payAmountCents <= 0) {
    passed = false
    message = '确认付款金额必须大于 0。'
  } else if (amounts.unpaidAmountInvalid || amounts.unpaidAmountEmpty) {
    passed = false
    message = '未付款金额缺失或无效，请检查未付款金额字段。'
  } else if (amounts.unpaidAmountCents <= 0) {
    passed = false
    message = '未付款金额必须大于 0。'
  } else if (amounts.payAmountCents > amounts.unpaidAmountCents) {
    passed = false
    message = '确认付款金额不能超过未付款金额。'
  } else if (amounts.decimalOverflow) {
    passed = false
    message = '金额应保留两位小数。'
  }
  const usedText = `检查使用付款金额 ${amounts.payAmount.toFixed(2)}，检查使用未付款金额 ${amounts.unpaidAmount.toFixed(2)}。`
  return buildReviewItem(
    'amount',
    '金额检查',
    passed,
    `${message} ${usedText}`,
    'error',
    '请检查付款金额、未付款金额和金额字段来源后重新评审。',
    {
      message: passed ? `金额检查通过。${usedText}` : `${message} ${usedText}`,
      checkedPayAmount: amounts.payAmount,
      checkedUnpaidAmount: amounts.unpaidAmount,
      checkedPayAmountField: amounts.payAmountField,
      checkedUnpaidAmountField: amounts.unpaidAmountField,
    },
  )
}

function buildReviewItems(draft = {}) {
  const sourceOk = hasText(draft.sourceInvoicePrepareNo)
    && hasText(draft.sourceApDraftNo)
    && hasText(draft.sourcePayableCheckNo)
    && hasText(draft.sourcePurchaseOrderNo)
  const amounts = resolvePaymentRiskAmounts(draft)
  const mockBank = hasMockBankInfo(draft)
  return [
    buildReviewItem(
      'paymentOrderStatus',
      '付款单状态检查',
      draft.paymentOrderStatus === 'paymentReady',
      '必须来自“可进入真实付款”的正式付款单草稿。',
      'error',
      '请先在正式付款单草稿中完成付款执行确认并标记可进入真实付款。',
    ),
    buildReviewItem(
      'supplierBank',
      '供应商银行账户检查',
      hasText(draft.supplierBankName) && hasText(draft.supplierBankAccount) && hasText(draft.supplierBankAccountName),
      '供应商开户行、收款账号或账户名称不完整。',
      'error',
      '请维护真实供应商银行账户后重新评审。',
    ),
    buildReviewItem(
      'companyPaymentAccount',
      '企业付款账户检查',
      hasText(draft.paymentBankName) && hasText(draft.paymentAccount) && hasText(draft.paymentAccountName),
      '企业付款银行、付款账号或账户名称不完整。',
      'error',
      '请维护企业真实付款账户后重新评审。',
    ),
    buildAmountReview(amounts),
    buildReviewItem(
      'sourceTrace',
      '发票与应付链路检查',
      sourceOk,
      '发票预备、应付账款草稿、应付核对或采购订单来源追踪不完整。',
      'error',
      '请返回前序链路补齐来源后重新评审。',
    ),
    buildReviewItem(
      'duplicatePayment',
      '防重复付款检查',
      !hasDuplicatePaymentRisk(draft),
      '检测到可能已有真实付款草稿或付款执行记录。',
      'error',
      '请确认没有重复付款记录后再重新评审。',
    ),
    buildReviewItem(
      'approval',
      '审批检查',
      draft.paymentConfirmed === true || draft.paymentOrderStatus === 'paymentReady',
      '正式付款单草稿尚未完成付款执行确认；后续真实付款仍需单独审批。',
      'warning',
      '请先完成付款执行确认；后续真实付款模块必须再做独立审批。',
    ),
    buildReviewItem(
      'financeBoundary',
      '财务边界检查',
      true,
      '',
      'info',
      '',
    ),
    buildReviewItem(
      'mockBankInfo',
      '模拟银行信息检查',
      !mockBank,
      '当前银行信息为模拟数据，仅用于本地流程验证，不能用于真实付款。',
      'error',
      '请维护真实供应商银行账户和企业付款账户后重新评审。',
    ),
  ]
}

function summarizeItems(items = []) {
  const blocked = items.filter((item) => item.result === 'blocked')
  const warnings = items.filter((item) => item.result === 'warning')
  if (blocked.length) {
    return {
      riskReviewStatus: 'blocked',
      riskLevel: 'blocked',
      blockingReasons: blocked.map((item) => item.message),
      warningReasons: warnings.map((item) => item.message),
      nextSuggestion: blocked.some((item) => item.key === 'mockBankInfo')
        ? '请维护真实银行资料后重新执行风险评审。'
        : '请先处理阻断项，再重新执行风险评审。',
    }
  }
  if (warnings.length) {
    return {
      riskReviewStatus: 'warning',
      riskLevel: 'medium',
      blockingReasons: [],
      warningReasons: warnings.map((item) => item.message),
      nextSuggestion: '请确认警告项已被业务负责人知悉，后续真实付款仍需独立审批。',
    }
  }
  return {
    riskReviewStatus: 'passed',
    riskLevel: 'low',
    blockingReasons: [],
    warningReasons: [],
    nextSuggestion: '风险评审通过；后续真实付款模块仍需单独审批和执行。',
  }
}

function buildReviewFromDraft(draft = {}, existing = null) {
  const amounts = resolvePaymentRiskAmounts(draft)
  const items = buildReviewItems(draft)
  const summary = summarizeItems(items)
  const now = nowText()
  return normalizeReviewResult({
    ...existing,
    id: existing?.id || createId('per'),
    riskReviewNo: existing?.riskReviewNo || createNo('PER'),
    sourcePaymentOrderDraftId: draft.id,
    sourcePaymentOrderDraftNo: draft.paymentOrderDraftNo,
    sourcePaymentPrepareNo: draft.sourcePaymentPrepareNo,
    sourcePaymentDraftNo: draft.sourcePaymentDraftNo,
    sourceApDraftNo: draft.sourceApDraftNo,
    sourceInvoicePrepareNo: draft.sourceInvoicePrepareNo,
    sourcePayableCheckNo: draft.sourcePayableCheckNo,
    sourcePayablePrepareNo: draft.sourcePayablePrepareNo,
    sourcePurchaseOrderNo: draft.sourcePurchaseOrderNo,
    sourceReceiveNo: draft.sourceReceiveNo,
    sourceInspectionNo: draft.sourceInspectionNo,
    sourceInventoryTransactionNos: sourceInventoryText(draft),
    rootRequestNo: draft.rootRequestNo,
    supplierId: draft.supplierId,
    supplierName: draft.supplierName,
    paymentAccount: draft.paymentAccount,
    paymentAccountName: draft.paymentAccountName,
    paymentBankName: draft.paymentBankName,
    supplierBankName: draft.supplierBankName,
    supplierBankAccount: draft.supplierBankAccount,
    supplierBankAccountName: draft.supplierBankAccountName,
    confirmedPayAmount: amounts.payAmount,
    unpaidAmount: amounts.unpaidAmount,
    checkPayAmount: amounts.payAmount,
    checkUnpaidAmount: amounts.unpaidAmount,
    checkPayAmountField: amounts.payAmountField,
    checkUnpaidAmountField: amounts.unpaidAmountField,
    paymentOrderStatus: draft.paymentOrderStatus,
    voucherStatus: draft.voucherStatus,
    bankPaymentStatus: draft.bankPaymentStatus,
    bankInfoMocked: hasMockBankInfo(draft),
    paymentBankInfoMocked: Boolean(draft.paymentBankInfoMocked),
    supplierBankInfoMocked: Boolean(draft.supplierBankInfoMocked),
    bankInfoMockRemark: draft.bankInfoMockRemark || '',
    reviewItems: items,
    reviewedAt: now,
    reviewedBy: '系统演示用户',
    updatedAt: now,
    ...summary,
  })
}

export function getPaymentExecutionRiskReviewState() {
  return clone(state)
}

export function listPaymentExecutionRiskReviews() {
  return clone(state.reviewResults)
}

export function getPaymentExecutionRiskReviewById(id) {
  return clone(byId(state.reviewResults, id))
}

export function getPaymentRiskReviewSources() {
  const reviews = state.reviewResults
  return listPaymentOrderDrafts()
    .filter((draft) => draft.paymentOrderStatus === 'paymentReady')
    .map((draft) => {
      const existing = reviews.find((review) => String(review.sourcePaymentOrderDraftId) === String(draft.id) && review.riskReviewStatus !== 'cancelled')
      const amounts = resolvePaymentRiskAmounts(draft)
      return {
        ...draft,
        confirmedPayAmount: amounts.payAmount,
        unpaidAmount: amounts.unpaidAmount,
        checkPayAmount: amounts.payAmount,
        checkUnpaidAmount: amounts.unpaidAmount,
        checkPayAmountField: amounts.payAmountField,
        checkUnpaidAmountField: amounts.unpaidAmountField,
        sourceInventoryTransactionNos: sourceInventoryText(draft),
        riskReviewGenerated: Boolean(existing),
        riskReviewId: existing?.id || '',
        riskReviewNo: existing?.riskReviewNo || '',
        riskReviewStatus: existing?.riskReviewStatus || '',
        riskLevel: existing?.riskLevel || '',
        bankInfoMocked: hasMockBankInfo(draft),
        canRunRiskReview: draft.paymentOrderStatus === 'paymentReady',
      }
    })
}

export function runPaymentExecutionRiskReview(sourceId) {
  const draft = getPaymentOrderDraftById(sourceId)
  if (!draft) return { success: false, error: '未找到正式付款单草稿。' }
  const existing = byDraftId(sourceId)
  const review = buildReviewFromDraft(draft, existing)
  const amountItem = (review.reviewItems || []).find((item) => item.key === 'amount')
  if (existing) {
    Object.assign(existing, review)
  } else {
    state.reviewResults.unshift(review)
  }
  persist()
  writeRiskReviewLog('执行真实付款风险评审', {
    sourceNo: draft.paymentOrderDraftNo,
    targetId: review.id,
    targetNo: review.riskReviewNo,
    result: `${review.riskReviewStatus} / ${review.riskLevel}`,
  })
  writeRiskReviewLog('付款金额字段归一化', { sourceNo: draft.paymentOrderDraftNo, targetId: review.id, targetNo: review.riskReviewNo, result: `${review.checkPayAmountField || '-'} = ${review.checkPayAmount}` })
  writeRiskReviewLog('未付款金额字段归一化', { sourceNo: draft.paymentOrderDraftNo, targetId: review.id, targetNo: review.riskReviewNo, result: `${review.checkUnpaidAmountField || '-'} = ${review.checkUnpaidAmount}` })
  writeRiskReviewLog('修复后执行金额检查', { sourceNo: draft.paymentOrderDraftNo, targetId: review.id, targetNo: review.riskReviewNo, result: amountItem?.message || '-' })
  writeRiskReviewLog(amountItem?.passed ? '金额检查通过' : '金额检查阻断原因', { sourceNo: draft.paymentOrderDraftNo, targetId: review.id, targetNo: review.riskReviewNo, result: amountItem?.message || '-' })
  if (existing) writeRiskReviewLog('重新评审更新金额检查结果', { sourceNo: draft.paymentOrderDraftNo, targetId: review.id, targetNo: review.riskReviewNo, result: amountItem?.message || '-' })
  if (review.bankInfoMocked) writeRiskReviewLog('检测到模拟银行信息', { sourceNo: draft.paymentOrderDraftNo, targetId: review.id, targetNo: review.riskReviewNo, result: '阻断' })
  if (review.blockingReasons.some((reason) => reason.includes('重复付款'))) writeRiskReviewLog('检测到重复付款风险', { sourceNo: draft.paymentOrderDraftNo, targetId: review.id, targetNo: review.riskReviewNo, result: '阻断' })
  if (review.riskReviewStatus === 'passed') writeRiskReviewLog('风险评审通过', { sourceNo: draft.paymentOrderDraftNo, targetId: review.id, targetNo: review.riskReviewNo })
  if (review.riskReviewStatus === 'blocked') writeRiskReviewLog('风险评审阻断', { sourceNo: draft.paymentOrderDraftNo, targetId: review.id, targetNo: review.riskReviewNo, result: review.blockingReasons.join('；') })
  return { success: true, review: clone(review) }
}

export function rerunPaymentExecutionRiskReview(reviewId) {
  const current = byId(state.reviewResults, reviewId)
  if (!current) return { success: false, error: '未找到风险评审记录。' }
  return runPaymentExecutionRiskReview(current.sourcePaymentOrderDraftId)
}

export function markPaymentExecutionRiskReviewPassed(reviewId) {
  const current = byId(state.reviewResults, reviewId)
  if (!current) return { success: false, error: '未找到风险评审记录。' }
  if (current.riskReviewStatus === 'passed' && current.riskLevel === 'low') {
    writeRiskReviewLog('风险评审通过已达成', { sourceNo: current.sourcePaymentOrderDraftNo, targetId: current.id, targetNo: current.riskReviewNo, result: '该风险评审已通过，无需重复标记。' })
    return { success: true, alreadyDone: true, review: clone(current), message: '该风险评审已通过，无需重复标记。' }
  }
  Object.assign(current, {
    riskReviewStatus: 'passed',
    riskLevel: current.warningReasons.length ? 'medium' : 'low',
    blockingReasons: [],
    updatedAt: nowText(),
  })
  persist()
  writeRiskReviewLog('人工标记风险评审通过', { sourceNo: current.sourcePaymentOrderDraftNo, targetId: current.id, targetNo: current.riskReviewNo, result: '人工确认风险已处理；本动作不执行真实付款。' })
  return { success: true, review: clone(current) }
}

export function markPaymentExecutionRiskReviewBlocked(reviewId) {
  const current = byId(state.reviewResults, reviewId)
  if (!current) return { success: false, error: '未找到风险评审记录。' }
  Object.assign(current, {
    riskReviewStatus: 'blocked',
    riskLevel: 'blocked',
    blockingReasons: current.blockingReasons.length ? current.blockingReasons : ['已手工标记为评审阻断。'],
    updatedAt: nowText(),
  })
  persist()
  writeRiskReviewLog('风险评审阻断', { sourceNo: current.sourcePaymentOrderDraftNo, targetId: current.id, targetNo: current.riskReviewNo, result: current.blockingReasons.join('；') })
  return { success: true, review: clone(current) }
}

export function cancelPaymentExecutionRiskReview(reviewId) {
  const current = byId(state.reviewResults, reviewId)
  if (!current) return { success: false, error: '未找到风险评审记录。' }
  Object.assign(current, { riskReviewStatus: 'cancelled', riskLevel: 'medium', cancelledAt: nowText(), updatedAt: nowText() })
  persist()
  writeRiskReviewLog('取消风险评审', { sourceNo: current.sourcePaymentOrderDraftNo, targetId: current.id, targetNo: current.riskReviewNo })
  return { success: true, review: clone(current) }
}

function batchResult(ids = [], handler, label, noGetter = (id) => id) {
  const result = { total: ids.length, successCount: 0, alreadyDoneCount: 0, blockedCount: 0, warningCount: 0, failedCount: 0, successItems: [], alreadyDoneItems: [], failedReason: [], nextSuggestion: '' }
  ids.forEach((id) => {
    const no = noGetter(id)
    const outcome = handler(id)
    if (!outcome?.success) {
      const reason = outcome?.error || '当前记录不满足批量操作条件。'
      result.failedCount += 1
      result.failedReason.push(`${no}：${reason}`)
      return
    }
    const review = outcome.review || {}
    if (outcome.alreadyDone) result.alreadyDoneCount += 1
    else if (review.riskReviewStatus === 'blocked') result.blockedCount += 1
    else if (review.riskReviewStatus === 'warning') result.warningCount += 1
    else result.successCount += 1
    if (outcome.alreadyDone) result.alreadyDoneItems.push({ id, no, status: review.riskReviewStatus, riskLevel: review.riskLevel })
    result.successItems.push({ id, no, status: review.riskReviewStatus, riskLevel: review.riskLevel })
  })
  result.nextSuggestion = result.blockedCount
    ? '请先处理阻断项，尤其是模拟银行信息、账户和来源链路问题。'
    : (result.warningCount ? '请确认警告项并保留后续真实付款审批。' : '评审通过或已达成后，后续真实付款仍需独立审批与执行。')
  writeRiskReviewLog(label, { targetType: 'batch', targetId: label, result: `通过 ${result.successCount} 条，已达成 ${result.alreadyDoneCount} 条，警告 ${result.warningCount} 条，阻断 ${result.blockedCount} 条，失败 ${result.failedCount} 条；${result.failedReason.join('；')}` })
  return result
}

export function batchRunPaymentExecutionRiskReviews(ids = []) {
  return batchResult(ids, runPaymentExecutionRiskReview, '批量执行风险评审', (id) => getPaymentOrderDraftById(id)?.paymentOrderDraftNo || id)
}

export function batchRerunPaymentExecutionRiskReviews(ids = []) {
  return batchResult(ids, rerunPaymentExecutionRiskReview, '批量重新评审', (id) => byId(state.reviewResults, id)?.riskReviewNo || id)
}

export function batchCancelPaymentExecutionRiskReviews(ids = []) {
  return batchResult(ids, cancelPaymentExecutionRiskReview, '批量取消风险评审', (id) => byId(state.reviewResults, id)?.riskReviewNo || id)
}
