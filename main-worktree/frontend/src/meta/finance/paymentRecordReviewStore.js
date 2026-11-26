import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  getPaymentExecutionById,
  listPaymentExecutions,
  markPaymentExecutionPaymentRecordReviewGenerated,
  markPaymentExecutionPaymentRecordReviewStatus,
} from './paymentExecutionStore.js'

const STORAGE_KEY = 'payment-record-review-state-v1'
const ACTIVE_REVIEW_STATUSES = ['pending', 'reviewing', 'passed', 'rejected']
const LOCAL_REVIEWER_REMARK = '当前为本地演示复核人，后续需接入正式登录用户'

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

function normalizeLine(line = {}, index = 0, source = {}) {
  const executionAmount = toSafeAmount(line.executionAmount ?? line.payableAmount ?? source.executionAmount)
  return {
    id: line.id || createId('prrl'),
    lineNo: line.lineNo || index + 1,
    materialId: line.materialId || '',
    materialCode: line.materialCode || '',
    materialName: line.materialName || line.itemName || '付款记录复核明细',
    spec: line.spec || '',
    unit: line.unit || '',
    payableAmount: toSafeAmount(line.payableAmount ?? executionAmount),
    paidAmount: toSafeAmount(line.paidAmount ?? 0),
    unpaidAmount: toSafeAmount(line.unpaidAmount ?? source.unpaidAmount ?? executionAmount),
    executionAmount,
    sourcePurchaseOrderNo: line.sourcePurchaseOrderNo || source.sourcePurchaseOrderNo || '',
    sourceReceiveNo: line.sourceReceiveNo || source.sourceReceiveNo || '',
    sourceInspectionNo: line.sourceInspectionNo || source.sourceInspectionNo || '',
    sourceInventoryTransactionNo: line.sourceInventoryTransactionNo || (source.sourceInventoryTransactionNos || [])[0] || '',
    rootRequestNo: line.rootRequestNo || source.rootRequestNo || '',
    remark: line.remark || '',
  }
}

function normalizeReview(item = {}) {
  const lines = Array.isArray(item.lines) && item.lines.length
    ? item.lines.map((line, index) => normalizeLine(line, index, item))
    : [normalizeLine({}, 0, item)]
  const executionAmount = toSafeAmount(item.executionAmount ?? lines.reduce((sum, line) => sum + toSafeAmount(line.executionAmount), 0))
  return {
    id: item.id || createId('prr'),
    paymentRecordReviewNo: item.paymentRecordReviewNo || createNo('PRR'),
    sourcePaymentExecutionId: item.sourcePaymentExecutionId || '',
    sourcePaymentExecutionNo: item.sourcePaymentExecutionNo || '',
    sourceRiskReviewNo: item.sourceRiskReviewNo || '',
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
    paymentAccountName: item.paymentAccountName || '',
    paymentBankName: item.paymentBankName || '',
    paymentAccount: item.paymentAccount || '',
    supplierBankName: item.supplierBankName || '',
    supplierBankAccount: item.supplierBankAccount || '',
    supplierBankAccountName: item.supplierBankAccountName || '',
    totalPayableAmount: toSafeAmount(item.totalPayableAmount ?? executionAmount),
    paidAmount: toSafeAmount(item.paidAmount ?? 0),
    unpaidAmount: toSafeAmount(item.unpaidAmount ?? executionAmount),
    executionAmount,
    expectedPayDate: item.expectedPayDate || '',
    actualPayDate: item.actualPayDate || '',
    offlinePaymentRecordNo: item.offlinePaymentRecordNo || '',
    offlinePaymentRemark: item.offlinePaymentRemark || '',
    offlinePaymentRecordedBy: item.offlinePaymentRecordedBy || '线下登记员',
    offlinePaymentRecordedAt: item.offlinePaymentRecordedAt || item.offlineRecordedAt || '',
    reviewStatus: item.reviewStatus || 'pending',
    reviewResult: item.reviewResult || 'notReviewed',
    reviewOpinion: item.reviewOpinion || '',
    currentReviewerId: item.currentReviewerId || '',
    currentReviewerName: item.currentReviewerName || '',
    currentReviewerRole: item.currentReviewerRole || '',
    currentReviewerSource: item.currentReviewerSource || '',
    currentReviewerSourceRemark: item.currentReviewerSourceRemark || '',
    reviewStartedAt: item.reviewStartedAt || '',
    reviewerId: item.reviewerId || '',
    reviewer: item.reviewer || item.reviewerName || '',
    reviewerName: item.reviewerName || item.reviewer || '',
    reviewerRole: item.reviewerRole || '',
    reviewRole: item.reviewRole || '',
    roleName: item.roleName || '',
    reviewerSource: item.reviewerSource || '',
    reviewerSourceRemark: item.reviewerSourceRemark || '',
    reviewedAt: item.reviewedAt || '',
    realPaymentStatus: item.realPaymentStatus || 'offlineRecorded',
    voucherStatus: item.voucherStatus || 'notGenerated',
    paymentVoucherDraftGenerated: Boolean(item.paymentVoucherDraftGenerated),
    targetPaymentVoucherDraftId: item.targetPaymentVoucherDraftId || '',
    targetPaymentVoucherDraftNo: item.targetPaymentVoucherDraftNo || '',
    paymentVoucherDraftStatus: item.paymentVoucherDraftStatus || '',
    paymentVoucherDraftGeneratedAt: item.paymentVoucherDraftGeneratedAt || '',
    voucherReviewStatus: item.voucherReviewStatus || '',
    targetModule: item.targetModule || '',
    ledgerStatus: item.ledgerStatus || 'notPosted',
    createdAt: item.createdAt || nowText(),
    updatedAt: item.updatedAt || nowText(),
    lines,
  }
}

function defaultState() {
  return { paymentRecordReviews: [] }
}

function normalizeState(raw = {}) {
  return {
    paymentRecordReviews: (raw.paymentRecordReviews || []).map(normalizeReview),
  }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[PAYMENT RECORD REVIEW STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function byId(id) {
  return state.paymentRecordReviews.find((item) => String(item.id) === String(id)) || null
}

function activeByPaymentExecutionId(paymentExecutionId) {
  return state.paymentRecordReviews.find((item) => (
    String(item.sourcePaymentExecutionId) === String(paymentExecutionId)
    && ACTIVE_REVIEW_STATUSES.includes(item.reviewStatus)
  )) || null
}

export function writePaymentRecordReviewLog(action, payload = {}) {
  addOperationLog({
    module: '付款记录复核',
    action,
    targetType: payload.targetType || 'paymentRecordReview',
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

function normalizeReviewer(source = {}, sourceType = '') {
  if (!source || typeof source !== 'object') return null
  const reviewerName = source.reviewerName
    || source.reviewer
    || source.name
    || source.userName
    || source.displayName
    || source.realName
    || source.employeeName
    || ''
  if (!hasText(reviewerName)) return null
  return {
    reviewerId: source.reviewerId || source.id || source.userId || source.employeeId || source.code || '',
    reviewerName,
    reviewerRole: source.reviewerRole || source.role || source.roleName || source.jobName || source.position || '付款记录复核',
    reviewerSource: source.reviewerSource || sourceType || 'currentUser',
  }
}

function readLocalJson(key) {
  if (typeof localStorage === 'undefined') return null
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch (error) {
    return null
  }
}

function resolveStoredCurrentUser() {
  const keys = ['currentUser', 'currentOperator', 'runtimeUser', 'loginUser', 'profitos-current-user']
  for (const key of keys) {
    const reviewer = normalizeReviewer(readLocalJson(key), 'currentUser')
    if (reviewer) return reviewer
  }
  return null
}

function flattenPeople(value, bucket = []) {
  if (!value || bucket.length > 200) return bucket
  if (Array.isArray(value)) {
    value.forEach((item) => flattenPeople(item, bucket))
    return bucket
  }
  if (typeof value !== 'object') return bucket
  if (hasText(value.name) || hasText(value.employeeName) || hasText(value.userName) || hasText(value.reviewerName)) {
    bucket.push(value)
  }
  Object.keys(value).forEach((key) => {
    if (['employees', 'users', 'staff', 'personnel', 'members', 'operators'].includes(key)) {
      flattenPeople(value[key], bucket)
    }
  })
  return bucket
}

function resolveOrganizationReviewer() {
  const keys = ['organization-state-v1', 'manufacturing-foundation-state-v1', 'foundation-organization-state-v1']
  const roleKeywords = ['财务复核人', '财务经理', '出纳主管', '应付复核岗']
  for (const key of keys) {
    const people = flattenPeople(readLocalJson(key))
    const matched = people.find((person) => {
      const text = [
        person.reviewerRole,
        person.role,
        person.roleName,
        person.jobName,
        person.position,
        person.name,
        person.employeeName,
      ].join(' ')
      return roleKeywords.some((keyword) => text.includes(keyword))
    })
    const reviewer = normalizeReviewer(matched, 'organization')
    if (reviewer) return reviewer
  }
  return null
}

export function getPaymentRecordReviewerSourceLabel(source) {
  return {
    currentUser: '当前登录用户',
    currentOperator: '当前操作人',
    organization: '组织人员档案',
    workflow: '审批流配置',
    localDemo: '本地演示复核人',
  }[source] || source || '-'
}

export function resolveCurrentReviewer(payload = {}) {
  const payloadReviewer = normalizeReviewer(
    payload.currentUser || payload.currentOperator || payload.runtimeUser || payload.loginUser,
    'currentUser',
  )
  const manualReviewer = normalizeReviewer(payload, 'currentOperator')
  const reviewer = payloadReviewer || manualReviewer || resolveStoredCurrentUser() || resolveOrganizationReviewer() || {
    reviewerId: 'LOCAL-REVIEWER',
    reviewerName: '当前复核人',
    reviewerRole: '付款记录复核',
    reviewerSource: 'localDemo',
  }

  if (!payload.silent) {
    writePaymentRecordReviewLog('解析当前复核人', {
      result: `复核人：${reviewer.reviewerName}；来源：${getPaymentRecordReviewerSourceLabel(reviewer.reviewerSource)}`,
    })
  }
  if (!payload.silent && reviewer.reviewerSource === 'localDemo') {
    writePaymentRecordReviewLog('使用本地演示复核人', {
      result: LOCAL_REVIEWER_REMARK,
    })
  }
  return reviewer
}

function reviewerPatch(reviewer = {}) {
  return {
    reviewerId: reviewer.reviewerId || '',
    reviewer: reviewer.reviewerName || '',
    reviewerName: reviewer.reviewerName || '',
    reviewerRole: reviewer.reviewerRole || '',
    reviewRole: reviewer.reviewerRole || '',
    roleName: reviewer.reviewerRole || '',
    reviewerSource: reviewer.reviewerSource || '',
    reviewerSourceRemark: reviewer.reviewerSource === 'localDemo' ? LOCAL_REVIEWER_REMARK : '',
  }
}

function canCreateFromExecution(execution = {}) {
  if (!execution?.id) return '未找到付款执行草稿。'
  if (execution.paymentExecutionStatus !== 'recordReviewPending') return '只有付款记录待复核状态可以生成复核任务。'
  if (!execution.offlinePaymentRecorded) return '尚未登记线下付款结果草稿。'
  if (!hasText(execution.offlinePaymentRecordNo) && !hasText(execution.offlinePaymentRemark)) return '缺少线下付款记录草稿号或线下结果说明。'
  if (execution.realPaymentStatus !== 'offlineRecorded') return '真实付款状态必须为已登记线下付款结果草稿。'
  if (activeByPaymentExecutionId(execution.id)) return '该付款执行草稿已生成付款记录复核任务，不能重复生成。'
  return ''
}

function buildReviewFromExecution(execution = {}) {
  return normalizeReview({
    sourcePaymentExecutionId: execution.id,
    sourcePaymentExecutionNo: execution.paymentExecutionNo,
    sourceRiskReviewNo: execution.sourceRiskReviewNo,
    sourcePaymentOrderDraftNo: execution.sourcePaymentOrderDraftNo,
    sourcePaymentPrepareNo: execution.sourcePaymentPrepareNo,
    sourcePaymentDraftNo: execution.sourcePaymentDraftNo,
    sourceApDraftNo: execution.sourceApDraftNo,
    sourceInvoicePrepareNo: execution.sourceInvoicePrepareNo,
    sourcePayableCheckNo: execution.sourcePayableCheckNo,
    sourcePayablePrepareNo: execution.sourcePayablePrepareNo,
    sourceInventoryTransactionNos: execution.sourceInventoryTransactionNos || [],
    sourceInspectionNo: execution.sourceInspectionNo,
    sourceReceiveNo: execution.sourceReceiveNo,
    sourcePurchaseOrderNo: execution.sourcePurchaseOrderNo,
    rootRequestNo: execution.rootRequestNo,
    supplierId: execution.supplierId,
    supplierName: execution.supplierName,
    paymentAccountName: execution.paymentAccountName,
    paymentBankName: execution.paymentBankName,
    paymentAccount: execution.paymentAccount,
    supplierBankName: execution.supplierBankName,
    supplierBankAccount: execution.supplierBankAccount,
    supplierBankAccountName: execution.supplierBankAccountName,
    totalPayableAmount: execution.executionAmount,
    paidAmount: 0,
    unpaidAmount: execution.unpaidAmount,
    executionAmount: execution.executionAmount,
    expectedPayDate: execution.expectedPayDate,
    actualPayDate: execution.actualPayDate,
    offlinePaymentRecordNo: execution.offlinePaymentRecordNo,
    offlinePaymentRemark: execution.offlinePaymentRemark,
    offlinePaymentRecordedAt: execution.offlineRecordedAt,
    realPaymentStatus: 'offlineRecorded',
    voucherStatus: 'notGenerated',
    ledgerStatus: 'notPosted',
    lines: execution.lines || [],
  })
}

export function getPaymentRecordReviewState() {
  return clone(state)
}

export function savePaymentRecordReviewState(nextState = {}) {
  state = normalizeState(nextState)
  persist()
  return getPaymentRecordReviewState()
}

export function resetPaymentRecordReviewState() {
  state = defaultState()
  persist()
  return getPaymentRecordReviewState()
}

export function listPaymentRecordReviews() {
  return clone(state.paymentRecordReviews)
}

export function getPaymentRecordReviewById(id) {
  const item = byId(id)
  return item ? clone(item) : null
}

export function isPaymentRecordReviewGenerated(paymentExecutionId) {
  const existing = activeByPaymentExecutionId(paymentExecutionId)
  return existing ? clone(existing) : null
}

export function getPaymentRecordReviewByPaymentExecutionId(paymentExecutionId) {
  return isPaymentRecordReviewGenerated(paymentExecutionId)
}

export function markPaymentRecordReviewPaymentVoucherDraftGenerated(id, draft = {}) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款记录复核任务。' }
  Object.assign(current, {
    paymentVoucherDraftGenerated: true,
    targetPaymentVoucherDraftId: draft.id || draft.targetPaymentVoucherDraftId || current.targetPaymentVoucherDraftId || '',
    targetPaymentVoucherDraftNo: draft.voucherDraftNo || draft.targetPaymentVoucherDraftNo || current.targetPaymentVoucherDraftNo || '',
    targetModule: 'paymentVoucherDraft',
    paymentVoucherDraftStatus: draft.voucherStatus || current.paymentVoucherDraftStatus || 'draft',
    voucherReviewStatus: draft.reviewStatus || current.voucherReviewStatus || 'notSubmitted',
    paymentVoucherDraftGeneratedAt: current.paymentVoucherDraftGeneratedAt || nowText(),
    voucherStatus: 'voucherDraftReady',
    ledgerStatus: current.ledgerStatus || 'notPosted',
    updatedAt: nowText(),
  })
  persist()
  writePaymentRecordReviewLog('回写付款凭证草稿生成状态', {
    sourceNo: current.paymentRecordReviewNo,
    targetId: current.targetPaymentVoucherDraftId,
    targetNo: current.targetPaymentVoucherDraftNo,
    result: '已生成付款凭证草稿；不是正式财务凭证，不写总账。',
  })
  return { success: true, review: clone(current) }
}

export function markPaymentRecordReviewPaymentVoucherDraftStatus(id, draft = {}) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款记录复核任务。' }
  Object.assign(current, {
    paymentVoucherDraftGenerated: current.paymentVoucherDraftGenerated || Boolean(current.targetPaymentVoucherDraftId || draft.id),
    targetPaymentVoucherDraftId: draft.id || current.targetPaymentVoucherDraftId || '',
    targetPaymentVoucherDraftNo: draft.voucherDraftNo || current.targetPaymentVoucherDraftNo || '',
    targetModule: current.targetModule || 'paymentVoucherDraft',
    paymentVoucherDraftStatus: draft.voucherStatus || current.paymentVoucherDraftStatus || '',
    voucherReviewStatus: draft.reviewStatus || current.voucherReviewStatus || '',
    voucherStatus: draft.voucherStatus === 'readyForReview' ? 'voucherDraftReady' : current.voucherStatus,
    ledgerStatus: draft.ledgerStatus || current.ledgerStatus || 'notPosted',
    updatedAt: nowText(),
  })
  persist()
  writePaymentRecordReviewLog('同步付款凭证草稿状态', {
    sourceNo: current.paymentRecordReviewNo,
    targetId: current.targetPaymentVoucherDraftId,
    targetNo: current.targetPaymentVoucherDraftNo,
    result: `付款凭证草稿状态：${current.paymentVoucherDraftStatus || '-'}`,
  })
  return { success: true, review: clone(current) }
}

export function getPaymentRecordReviewSourcesFromPaymentExecutions() {
  return listPaymentExecutions().map((execution) => {
    const existing = activeByPaymentExecutionId(execution.id)
    const disabledReason = existing ? '该付款执行草稿已生成付款记录复核任务，不能重复生成。' : canCreateFromExecution(execution)
    return {
      ...execution,
      paymentRecordReviewGenerated: Boolean(existing),
      targetPaymentRecordReviewId: existing?.id || '',
      targetPaymentRecordReviewNo: existing?.paymentRecordReviewNo || '',
      paymentRecordReviewStatus: existing?.reviewStatus || '',
      canGeneratePaymentRecordReview: !disabledReason,
      disabledReason,
    }
  })
}

export function createPaymentRecordReviewFromPaymentExecution(paymentExecutionId) {
  const execution = getPaymentExecutionById(paymentExecutionId)
  if (!execution) return { success: false, error: '未找到付款执行草稿。' }
  const existing = activeByPaymentExecutionId(execution.id)
  if (existing) {
    markPaymentExecutionPaymentRecordReviewGenerated(execution.id, existing)
    writePaymentRecordReviewLog('防重复生成付款记录复核任务', {
      sourceNo: execution.paymentExecutionNo,
      targetId: existing.id,
      targetNo: existing.paymentRecordReviewNo,
      result: '已存在未关闭付款记录复核任务，无需重复生成。',
    })
    return {
      success: true,
      alreadyDone: true,
      review: clone(existing),
      message: '该付款执行草稿已生成付款记录复核任务，不能重复生成。',
    }
  }
  const disabledReason = canCreateFromExecution(execution)
  if (disabledReason) return { success: false, error: disabledReason }

  const review = buildReviewFromExecution(execution)
  state.paymentRecordReviews.unshift(review)
  persist()
  markPaymentExecutionPaymentRecordReviewGenerated(execution.id, review)
  writePaymentRecordReviewLog('生成付款记录复核任务', {
    sourceNo: execution.paymentExecutionNo,
    targetId: review.id,
    targetNo: review.paymentRecordReviewNo,
    result: '已生成付款记录复核任务；仍未执行真实付款。',
  })
  return { success: true, review: clone(review) }
}

function transitionPaymentRecordReview(id, config = {}) {
  const current = byId(id)
  if (!current) return { success: false, error: '未找到付款记录复核任务。' }
  if (current.reviewStatus === config.targetStatus) {
    return {
      success: true,
      alreadyDone: true,
      review: clone(current),
      message: config.alreadyDoneMessage || '当前状态已达成，无需重复操作。',
    }
  }
  if (!config.from.includes(current.reviewStatus)) {
    return { success: false, error: config.invalidMessage || '当前状态不允许执行该操作。' }
  }
  const patch = typeof config.patch === 'function' ? config.patch(current) : (config.patch || {})
  Object.assign(current, patch, {
    reviewStatus: config.targetStatus,
    updatedAt: nowText(),
  })
  persist()
  markPaymentExecutionPaymentRecordReviewStatus(current.sourcePaymentExecutionId, current)
  writePaymentRecordReviewLog(config.action, {
    sourceNo: current.sourcePaymentExecutionNo,
    targetId: current.id,
    targetNo: current.paymentRecordReviewNo,
    result: config.logResult || getPaymentRecordReviewStatusLabel(current.reviewStatus),
  })
  return { success: true, review: clone(current) }
}

export function startPaymentRecordReview(id, payload = {}) {
  const reviewer = resolveCurrentReviewer(payload)
  return transitionPaymentRecordReview(id, {
    from: ['pending', 'rejected'],
    targetStatus: 'reviewing',
    action: '开始付款记录复核',
    logResult: '已进入复核中；仍未执行真实付款。',
    invalidMessage: '只有待复核或已退回记录可以开始复核。',
    patch: () => ({
      reviewResult: 'notReviewed',
      reviewer: payload.reviewer || '复核员',
      reviewOpinion: payload.reviewOpinion || '',
      currentReviewerId: reviewer.reviewerId,
      currentReviewerName: reviewer.reviewerName,
      currentReviewerRole: reviewer.reviewerRole,
      currentReviewerSource: reviewer.reviewerSource,
      currentReviewerSourceRemark: reviewer.reviewerSource === 'localDemo' ? LOCAL_REVIEWER_REMARK : '',
      reviewStartedAt: nowText(),
    }),
  })
}

export function passPaymentRecordReview(id, payload = {}) {
  const reviewer = resolveCurrentReviewer(payload)
  return transitionPaymentRecordReview(id, {
    from: ['reviewing'],
    targetStatus: 'passed',
    action: '付款记录复核通过',
    logResult: '付款记录复核通过；不是银行付款成功，不生成凭证，不写总账。',
    alreadyDoneMessage: '该付款记录复核任务已通过，无需重复操作。',
    invalidMessage: '只有复核中的记录可以复核通过。',
    patch: () => ({
      reviewResult: 'passed',
      reviewOpinion: payload.reviewOpinion || '付款记录复核通过；本页不执行真实付款。',
      reviewer: payload.reviewer || '复核员',
      ...reviewerPatch(reviewer),
      reviewedAt: nowText(),
      realPaymentStatus: 'paymentRecordReviewed',
      voucherStatus: 'notGenerated',
      ledgerStatus: 'notPosted',
    }),
  })
}

export function rejectPaymentRecordReview(id, payload = {}) {
  const reviewer = resolveCurrentReviewer(payload)
  return transitionPaymentRecordReview(id, {
    from: ['reviewing'],
    targetStatus: 'rejected',
    action: '付款记录复核退回',
    logResult: '付款记录已退回，需重新复核。',
    invalidMessage: '只有复核中的记录可以退回。',
    patch: () => ({
      reviewResult: 'rejected',
      reviewOpinion: payload.reviewOpinion || '复核退回，请补充或核对线下付款记录草稿。',
      reviewer: payload.reviewer || '复核员',
      ...reviewerPatch(reviewer),
      reviewedAt: nowText(),
      realPaymentStatus: 'offlineRecorded',
      voucherStatus: 'notGenerated',
      ledgerStatus: 'notPosted',
    }),
  })
}

export function cancelPaymentRecordReview(id, payload = {}) {
  return transitionPaymentRecordReview(id, {
    from: ['pending', 'reviewing', 'rejected'],
    targetStatus: 'cancelled',
    action: '取消付款记录复核',
    logResult: '已取消复核任务；不影响真实付款状态。',
    invalidMessage: '当前状态不能取消付款记录复核。',
    patch: () => ({
      reviewResult: payload.reviewResult || 'notReviewed',
      reviewOpinion: payload.reviewOpinion || '取消复核任务。',
      reviewer: payload.reviewer || '',
      reviewedAt: payload.reviewedAt || '',
      realPaymentStatus: 'offlineRecorded',
      voucherStatus: 'notGenerated',
      ledgerStatus: 'notPosted',
    }),
  })
}

function batchResult(ids = [], handler, label, noGetter = (id) => id, options = {}) {
  const needsReviewer = options.includeReviewer || [startPaymentRecordReview, passPaymentRecordReview, rejectPaymentRecordReview].includes(handler)
  const batchReviewer = needsReviewer ? resolveCurrentReviewer() : null
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
    reviewerName: batchReviewer?.reviewerName || '',
    reviewerRole: batchReviewer?.reviewerRole || '',
    reviewerSource: batchReviewer?.reviewerSource || '',
    reviewerSourceLabel: batchReviewer ? getPaymentRecordReviewerSourceLabel(batchReviewer.reviewerSource) : '',
    reviewerSourceRemark: batchReviewer?.reviewerSource === 'localDemo' ? LOCAL_REVIEWER_REMARK : '',
  }
  ids.forEach((id) => {
    const no = noGetter(id)
    const outcome = batchReviewer ? handler(id, batchReviewer) : handler(id)
    if (!outcome?.success) {
      result.failedCount += 1
      result.failedReason.push(`${no}：${outcome?.error || '当前记录不满足批量操作条件。'}`)
      return
    }
    const review = outcome.review || {}
    if (outcome.alreadyDone) {
      result.alreadyDoneCount += 1
      result.alreadyDoneItems.push({ id, no, status: review.reviewStatus })
    } else {
      result.successCount += 1
      result.successItems.push({ id, no, status: review.reviewStatus })
    }
  })
  result.nextSuggestion = result.failedCount
    ? '请按失败原因处理后再重试；本批量动作不会执行真实付款。'
    : '本批量动作已完成或已达成；复核通过仍不代表银行付款成功。'
  writePaymentRecordReviewLog(label, {
    targetType: 'batchPaymentRecordReview',
    targetId: label,
    result: `成功 ${result.successCount} 条，已达成 ${result.alreadyDoneCount} 条，失败 ${result.failedCount} 条；${result.failedReason.join('；')}`,
  })
  if (batchReviewer) {
    writePaymentRecordReviewLog(`${label}记录复核人`, {
      targetType: 'batchPaymentRecordReview',
      targetId: label,
      result: `复核人：${batchReviewer.reviewerName}；来源：${getPaymentRecordReviewerSourceLabel(batchReviewer.reviewerSource)}`,
    })
  }
  return result
}

export function batchCreatePaymentRecordReviewsFromPaymentExecutions(ids = []) {
  return batchResult(ids, createPaymentRecordReviewFromPaymentExecution, '批量生成付款记录复核任务', (id) => getPaymentExecutionById(id)?.paymentExecutionNo || id)
}

export function batchStartPaymentRecordReviews(ids = []) {
  return batchResult(ids, startPaymentRecordReview, '批量开始复核', (id) => byId(id)?.paymentRecordReviewNo || id)
}

export function batchPassPaymentRecordReviews(ids = []) {
  return batchResult(ids, passPaymentRecordReview, '批量复核通过', (id) => byId(id)?.paymentRecordReviewNo || id)
}

export function batchRejectPaymentRecordReviews(ids = []) {
  return batchResult(ids, rejectPaymentRecordReview, '批量复核退回', (id) => byId(id)?.paymentRecordReviewNo || id)
}

export function batchCancelPaymentRecordReviews(ids = []) {
  return batchResult(ids, cancelPaymentRecordReview, '批量取消复核', (id) => byId(id)?.paymentRecordReviewNo || id)
}

export function getPaymentRecordReviewStatusLabel(status) {
  return {
    pending: '待复核',
    reviewing: '复核中',
    passed: '复核通过',
    rejected: '复核退回',
    cancelled: '取消',
    closed: '关闭',
  }[status] || status || '-'
}

export function getPaymentRecordReviewStatusType(status) {
  return {
    pending: 'info',
    reviewing: 'primary',
    passed: 'success',
    rejected: 'warning',
    cancelled: 'info',
    closed: 'info',
  }[status] || 'info'
}

export function getPaymentRecordReviewResultLabel(result) {
  return {
    notReviewed: '未复核',
    passed: '通过',
    rejected: '退回',
  }[result] || result || '-'
}

export function getPaymentRecordRealPaymentStatusLabel(status) {
  return {
    offlineRecorded: '已登记线下付款记录',
    paymentRecordReviewed: '付款记录已复核',
    notBankPaid: '未银行付款',
  }[status] || status || '-'
}

export function getPaymentRecordVoucherStatusLabel(status) {
  return {
    notGenerated: '未生成凭证',
    voucherDraftReady: '可进入凭证草稿',
  }[status] || status || '-'
}

export function getPaymentRecordLedgerStatusLabel(status) {
  return {
    notPosted: '未写总账',
  }[status] || status || '-'
}
