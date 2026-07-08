import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  buildPaymentPrepareSupplierBankFields,
  findSupplierProfileForPayment,
  getDefaultCompanyBankAccount,
  normalizePaymentMethod,
  writeBusinessPartnerLog,
} from '../foundation/businessPartnerStore.js'
import {
  getPaymentOrderPrepareById,
  listPaymentOrderPrepares,
} from './paymentOrderPrepareStore.js'

const STORAGE_KEY = 'payment-order-draft-state-v1'
const SOURCE_READY_STATUSES = ['ready', 'checked']
const ACTIVE_DRAFT_STATUSES = ['draft', 'checking', 'confirmed', 'paymentReady']
const CLOSED_DRAFT_STATUSES = ['cancelled', 'closed']

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

function defaultState() {
  return { paymentOrderDrafts: [] }
}

function byId(collection, id) {
  return (collection || []).find((item) => String(item.id) === String(id)) || null
}

function sourceInventoryText(row = {}) {
  const nos = row.sourceInventoryTransactionNos || row.sourceInventoryTransactionNo || ''
  if (Array.isArray(nos)) return nos.filter(Boolean)
  return nos ? [nos] : []
}

function normalizeLine(line = {}, index = 0) {
  const payableAmount = roundAmount(line.payableAmount)
  const paidAmount = roundAmount(line.paidAmount ?? 0)
  const unpaidAmount = roundAmount(line.unpaidAmount ?? Math.max(payableAmount - paidAmount, 0))
  const applyPayAmount = roundAmount(line.applyPayAmount ?? unpaidAmount)
  const approvedPayAmount = roundAmount(line.approvedPayAmount ?? applyPayAmount)
  const draftPayAmount = roundAmount(line.draftPayAmount ?? line.preparePayAmount ?? approvedPayAmount)
  const confirmedPayAmount = roundAmount(line.confirmedPayAmount ?? draftPayAmount)
  return {
    id: line.id || createId('podl'),
    lineNo: line.lineNo || index + 1,
    sourcePaymentPrepareLineId: line.sourcePaymentPrepareLineId || line.id || '',
    sourcePaymentDraftLineId: line.sourcePaymentDraftLineId || '',
    sourceApDraftLineId: line.sourceApDraftLineId || '',
    materialId: line.materialId || '',
    materialCode: line.materialCode || '',
    materialName: line.materialName || '',
    spec: line.spec || line.specification || '',
    unit: line.unit || '',
    payableAmount,
    paidAmount,
    unpaidAmount,
    applyPayAmount,
    approvedPayAmount,
    draftPayAmount: Math.min(Math.max(draftPayAmount, 0), unpaidAmount),
    confirmedPayAmount: Math.min(Math.max(confirmedPayAmount, 0), unpaidAmount),
    sourcePurchaseOrderNo: line.sourcePurchaseOrderNo || '',
    sourceReceiveNo: line.sourceReceiveNo || '',
    sourceInspectionNo: line.sourceInspectionNo || '',
    sourceInventoryTransactionNo: line.sourceInventoryTransactionNo || '',
    rootRequestNo: line.rootRequestNo || '',
    remark: line.remark || '',
  }
}

function paymentOrderDraft(payload = {}) {
  const stamp = nowText()
  const totalPayableAmount = roundAmount(payload.totalPayableAmount)
  const paidAmount = roundAmount(payload.paidAmount ?? 0)
  const unpaidAmount = roundAmount(payload.unpaidAmount ?? Math.max(totalPayableAmount - paidAmount, 0))
  const applyPayAmount = roundAmount(payload.applyPayAmount ?? unpaidAmount)
  const approvedPayAmount = roundAmount(payload.approvedPayAmount ?? applyPayAmount)
  const draftPayAmount = roundAmount(payload.draftPayAmount ?? payload.preparePayAmount ?? approvedPayAmount)
  const confirmedPayAmount = roundAmount(payload.confirmedPayAmount ?? draftPayAmount)
  return {
    id: payload.id || createId('pod'),
    paymentOrderDraftNo: payload.paymentOrderDraftNo || createNo('POD'),
    sourcePaymentPrepareId: payload.sourcePaymentPrepareId || '',
    sourcePaymentPrepareNo: payload.sourcePaymentPrepareNo || payload.paymentPrepareNo || '',
    sourcePaymentDraftId: payload.sourcePaymentDraftId || '',
    sourcePaymentDraftNo: payload.sourcePaymentDraftNo || '',
    sourceApDraftNo: payload.sourceApDraftNo || '',
    sourceInvoicePrepareNo: payload.sourceInvoicePrepareNo || '',
    sourcePayableCheckNo: payload.sourcePayableCheckNo || '',
    sourcePayablePrepareNo: payload.sourcePayablePrepareNo || '',
    supplierId: payload.supplierId || '',
    supplierName: payload.supplierName || '',
    sourcePurchaseOrderNo: payload.sourcePurchaseOrderNo || '',
    sourceReceiveNo: payload.sourceReceiveNo || '',
    sourceInspectionNo: payload.sourceInspectionNo || '',
    sourceInventoryTransactionNos: sourceInventoryText(payload),
    rootRequestNo: payload.rootRequestNo || '',
    paymentOrderStatus: payload.paymentOrderStatus || 'draft',
    draftDate: payload.draftDate || today(),
    confirmDate: payload.confirmDate || '',
    expectedPayDate: payload.expectedPayDate || payload.dueDate || '',
    actualPayDate: payload.actualPayDate || '',
    totalPayableAmount,
    paidAmount,
    unpaidAmount,
    applyPayAmount,
    approvedPayAmount,
    draftPayAmount: Math.min(Math.max(draftPayAmount, 0), unpaidAmount),
    confirmedPayAmount: Math.min(Math.max(confirmedPayAmount, 0), unpaidAmount),
    paymentMethod: payload.paymentMethod || 'bankTransfer',
    paymentAccount: payload.paymentAccount || '',
    paymentAccountName: payload.paymentAccountName || '',
    paymentBankName: payload.paymentBankName || '',
    supplierBankName: payload.supplierBankName || '',
    supplierBankAccount: payload.supplierBankAccount || '',
    supplierBankAccountName: payload.supplierBankAccountName || '',
    bankInfoMocked: payload.bankInfoMocked ?? false,
    bankInfoMockedAt: payload.bankInfoMockedAt || '',
    bankInfoMockRemark: payload.bankInfoMockRemark || '',
    executionCheckStatus: payload.executionCheckStatus || 'notChecked',
    executionCheckResult: payload.executionCheckResult || '',
    executionCheckItems: payload.executionCheckItems || [],
    paymentConfirmed: payload.paymentConfirmed ?? false,
    paymentConfirmedAt: payload.paymentConfirmedAt || '',
    paymentConfirmedBy: payload.paymentConfirmedBy || '',
    bankPaymentStatus: payload.bankPaymentStatus || 'notPaid',
    voucherStatus: payload.voucherStatus || 'notGenerated',
    remark: payload.remark || '',
    lines: (payload.lines || []).map(normalizeLine),
    createdAt: payload.createdAt || stamp,
    updatedAt: payload.updatedAt || stamp,
  }
}

function normalizeState(raw = {}) {
  return { paymentOrderDrafts: (raw.paymentOrderDrafts || []).map(paymentOrderDraft) }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[PAYMENT ORDER DRAFT STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function buildCheckItem(key, label, passed, message, severity = 'error', suggestion = '请按失败原因处理后重新执行付款确认检查。') {
  return {
    key,
    label,
    passed: Boolean(passed),
    message: passed ? '检查通过。' : message,
    severity: passed ? 'info' : severity,
    suggestion: passed ? '无需处理。' : suggestion,
  }
}

function paymentMethodText(method) {
  const normalized = normalizePaymentMethod(method)
  return { bankTransfer: '银行转账', cash: '现金', cheque: '支票', acceptance: '承兑', other: '其他' }[normalized] || normalized || '-'
}

function effectivePaymentDraftFields(record = {}, sourcePrepare = null) {
  const supplierProfile = findSupplierProfileForPayment({
    supplierId: record.supplierId || sourcePrepare?.supplierId,
    supplierCode: record.supplierCode || sourcePrepare?.supplierCode,
    supplierName: record.supplierName || sourcePrepare?.supplierName,
  })
  const supplierBankFields = supplierProfile ? buildPaymentPrepareSupplierBankFields(supplierProfile) : {}
  const companyAccount = getDefaultCompanyBankAccount()
  const paymentMethod = normalizePaymentMethod(
    record.paymentMethod
    || sourcePrepare?.paymentMethod
    || supplierBankFields.paymentMethod
    || 'bankTransfer',
  )
  return {
    supplierProfile,
    companyAccount,
    supplierId: record.supplierId || sourcePrepare?.supplierId || supplierProfile?.id || '',
    supplierName: record.supplierName || sourcePrepare?.supplierName || supplierProfile?.supplierName || '',
    supplierBankName: record.supplierBankName || sourcePrepare?.supplierBankName || supplierBankFields.supplierBankName || '',
    supplierBankAccount: record.supplierBankAccount || sourcePrepare?.supplierBankAccount || supplierBankFields.supplierBankAccount || '',
    supplierBankAccountName: record.supplierBankAccountName || sourcePrepare?.supplierBankAccountName || supplierBankFields.supplierBankAccountName || '',
    paymentMethod,
    paymentAccount: record.paymentAccount || sourcePrepare?.paymentAccount || companyAccount?.bankAccount || '',
    paymentAccountName: record.paymentAccountName || sourcePrepare?.paymentAccountName || companyAccount?.accountName || '',
    paymentBankName: record.paymentBankName || sourcePrepare?.paymentBankName || companyAccount?.bankName || '',
    bankInfoMocked: record.bankInfoMocked || sourcePrepare?.bankInfoMocked || supplierProfile?.bankInfoMocked || false,
    bankInfoMockedAt: record.bankInfoMockedAt || sourcePrepare?.bankInfoMockedAt || supplierProfile?.bankInfoMockedAt || '',
    bankInfoMockRemark: record.bankInfoMockRemark || sourcePrepare?.bankInfoMockRemark || supplierProfile?.bankInfoMockRemark || '',
  }
}

function buildMissingReasons(items = []) {
  return items.filter((item) => !item.ok).map((item) => item.text).join('；')
}

function applyPaymentDraftAutoPatch(record = {}, effective = {}) {
  const autoPatch = {}
  if (!record.supplierId && effective.supplierId) autoPatch.supplierId = effective.supplierId
  if (!record.supplierName && effective.supplierName) autoPatch.supplierName = effective.supplierName
  if (!record.supplierBankName && effective.supplierBankName) autoPatch.supplierBankName = effective.supplierBankName
  if (!record.supplierBankAccount && effective.supplierBankAccount) autoPatch.supplierBankAccount = effective.supplierBankAccount
  if (!record.supplierBankAccountName && effective.supplierBankAccountName) autoPatch.supplierBankAccountName = effective.supplierBankAccountName
  if (!record.paymentMethod && effective.paymentMethod) autoPatch.paymentMethod = effective.paymentMethod
  if (!record.paymentAccount && effective.paymentAccount) autoPatch.paymentAccount = effective.paymentAccount
  if (!record.paymentAccountName && effective.paymentAccountName) autoPatch.paymentAccountName = effective.paymentAccountName
  if (!record.paymentBankName && effective.paymentBankName) autoPatch.paymentBankName = effective.paymentBankName
  if (effective.bankInfoMocked && !record.bankInfoMocked) {
    autoPatch.bankInfoMocked = true
    autoPatch.bankInfoMockedAt = effective.bankInfoMockedAt || nowText()
    autoPatch.bankInfoMockRemark = effective.bankInfoMockRemark || '供应商银行信息为系统自动补齐模拟数据，仅用于流程验证。'
  }
  if (!record.id || !Object.keys(autoPatch).length) return autoPatch
  Object.assign(record, paymentOrderDraft({ ...record, ...autoPatch, id: record.id, createdAt: record.createdAt, updatedAt: nowText() }))
  persist()
  if (autoPatch.supplierBankName || autoPatch.supplierBankAccount || autoPatch.supplierBankAccountName) {
    writePaymentOrderDraftLog('付款执行检查自动补齐供应商收款信息', {
      targetId: record.id,
      targetNo: record.paymentOrderDraftNo,
      result: effective.supplierProfile?.supplierName || record.supplierName,
    })
  }
  if (autoPatch.paymentAccount || autoPatch.paymentAccountName || autoPatch.paymentBankName) {
    writePaymentOrderDraftLog('付款执行检查自动补齐企业付款账户', {
      targetId: record.id,
      targetNo: record.paymentOrderDraftNo,
      result: effective.companyAccount?.accountCode || effective.companyAccount?.bankName || '企业默认付款账户',
    })
  }
  return autoPatch
}

export function writePaymentOrderDraftLog(action, payload = {}) {
  addOperationLog({
    module: '正式付款单草稿',
    action,
    targetType: payload.targetType || 'paymentOrderDraft',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源单据：${payload.sourceNo || '-'}`,
      `目标单据：${payload.targetNo || '-'}`,
      `结果：${payload.result || '成功'}`,
    ].join('；'),
  })
}

export function getPaymentOrderDraftState() {
  return clone(state)
}

export function savePaymentOrderDraftState(nextState) {
  state = normalizeState(nextState)
  persist()
  writePaymentOrderDraftLog('保存正式付款单草稿状态', { targetType: 'paymentOrderDraftState', targetId: 'state' })
  return getPaymentOrderDraftState()
}

export function resetPaymentOrderDraftState() {
  state = defaultState()
  persist()
  writePaymentOrderDraftLog('恢复正式付款单草稿演示数据', { targetType: 'paymentOrderDraftState', targetId: 'demo' })
  return getPaymentOrderDraftState()
}

export function listPaymentOrderDrafts() {
  return clone(state.paymentOrderDrafts)
}

export function getPaymentOrderDraftById(id) {
  return clone(byId(state.paymentOrderDrafts, id))
}

export function isPaymentOrderDraftGenerated(paymentPrepareOrId) {
  const prepare = typeof paymentPrepareOrId === 'object' ? paymentPrepareOrId : getPaymentOrderPrepareById(paymentPrepareOrId)
  if (!prepare?.id) return false
  return state.paymentOrderDrafts.some((draft) => (
    String(draft.sourcePaymentPrepareId) === String(prepare.id)
    && ACTIVE_DRAFT_STATUSES.includes(draft.paymentOrderStatus)
  ))
}

function activeDraftByPrepare(prepare = {}) {
  return state.paymentOrderDrafts.find((draft) => (
    String(draft.sourcePaymentPrepareId) === String(prepare.id || '')
    && ACTIVE_DRAFT_STATUSES.includes(draft.paymentOrderStatus)
  )) || null
}

function sourceRejectReason(prepare = {}, writeDuplicateLog = false) {
  if (!prepare?.id) return '未找到正式付款单预备。'
  if (isPaymentOrderDraftGenerated(prepare)) {
    if (writeDuplicateLog) {
      writePaymentOrderDraftLog('防重复生成拦截', {
        sourceNo: prepare.paymentPrepareNo,
        result: '该正式付款单预备已生成正式付款单草稿，不能重复生成。',
      })
    }
    return '该正式付款单预备已生成正式付款单草稿，不能重复生成。'
  }
  if (prepare.preCheckStatus === 'blocked' || prepare.riskLevel === 'high') return '付款前检查未通过，不能生成正式付款单草稿。'
  if (!SOURCE_READY_STATUSES.includes(prepare.paymentPrepareStatus)) return '只有 ready 或 checked 状态的正式付款单预备可生成正式付款单草稿。'
  if (prepare.preCheckStatus === 'warning' && prepare.paymentPrepareStatus !== 'checked') return '付款前检查存在警告，请先标记已检查后再生成正式付款单草稿。'
  if (roundAmount(prepare.unpaidAmount) <= 0) return '未付款金额为 0，不能生成付款单草稿。'
  if (roundAmount(prepare.preparePayAmount) <= 0) return '预备付款金额为 0，不能生成付款单草稿。'
  if (roundAmount(prepare.preparePayAmount) > roundAmount(prepare.unpaidAmount)) return '预备付款金额不能大于未付款金额。'
  if (['blocked', 'cancelled', 'closed', 'draft', 'checking'].includes(prepare.paymentPrepareStatus)) return '当前付款预备状态不能生成付款单草稿。'
  return ''
}

export function getPaymentOrderDraftSourcesFromPaymentPrepares() {
  return listPaymentOrderPrepares().map((prepare) => {
    const existed = activeDraftByPrepare(prepare)
    const reason = sourceRejectReason(prepare)
    return {
      ...prepare,
      paymentOrderDraftGenerated: Boolean(existed),
      paymentOrderDraftGeneratedText: existed ? '已生成' : '未生成',
      targetPaymentOrderDraftId: existed?.id || '',
      targetPaymentOrderDraftNo: existed?.paymentOrderDraftNo || '',
      canCreatePaymentOrderDraft: !reason,
      sourceRejectReason: reason,
    }
  })
}

export function runPaymentExecutionCheck(recordOrId) {
  const record = typeof recordOrId === 'object'
    ? (recordOrId.id ? (byId(state.paymentOrderDrafts, recordOrId.id) || recordOrId) : recordOrId)
    : byId(state.paymentOrderDrafts, recordOrId)
  if (!record?.id) return { executionCheckStatus: 'blocked', executionCheckResult: '未找到正式付款单草稿。', executionCheckItems: [] }
  const sourcePrepare = record.sourcePaymentPrepareId ? getPaymentOrderPrepareById(record.sourcePaymentPrepareId) : null
  const effective = effectivePaymentDraftFields(record, sourcePrepare)
  applyPaymentDraftAutoPatch(record, effective)
  const duplicate = state.paymentOrderDrafts.some((draft) => (
    draft.id !== record.id
    && ACTIVE_DRAFT_STATUSES.includes(draft.paymentOrderStatus)
    && (
      String(draft.sourcePaymentPrepareId) === String(record.sourcePaymentPrepareId || '')
      || (record.sourcePaymentDraftId && String(draft.sourcePaymentDraftId) === String(record.sourcePaymentDraftId))
    )
  ))
  if (effective.supplierProfile) {
    writeBusinessPartnerLog('付款执行检查读取供应商档案', {
      targetType: 'paymentOrderDraft',
      targetId: record.id,
      targetNo: record.paymentOrderDraftNo,
      detail: effective.supplierProfile.supplierName,
    })
  } else {
    writeBusinessPartnerLog('付款执行检查未找到供应商档案', {
      targetType: 'paymentOrderDraft',
      targetId: record.id,
      targetNo: record.paymentOrderDraftNo,
      detail: record.supplierName || record.supplierId || '-',
    })
  }
  const supplierMissingReasons = buildMissingReasons([
    { ok: effective.supplierName, text: '缺少供应商名称' },
    { ok: effective.supplierProfile, text: '未找到供应商档案' },
    { ok: effective.supplierBankName, text: '供应商开户行缺失' },
    { ok: effective.supplierBankAccount, text: '供应商收款账号缺失' },
    { ok: effective.supplierBankAccountName, text: '供应商账户名称缺失' },
  ])
  const paymentMissingReasons = buildMissingReasons([
    { ok: effective.paymentMethod, text: '付款方式缺失' },
    { ok: effective.paymentBankName, text: '企业付款银行缺失' },
    { ok: effective.paymentAccount, text: '企业付款账号缺失' },
    { ok: effective.paymentAccountName, text: '企业付款账户名称缺失' },
  ])
  const supplierUsage = [
    `供应商：${effective.supplierName || '-'}`,
    `开户行：${effective.supplierBankName || '-'}`,
    `收款账号：${effective.supplierBankAccount || '-'}`,
    `账户名称：${effective.supplierBankAccountName || '-'}`,
    `来自供应商档案：${effective.supplierProfile ? '是' : '否'}`,
    `模拟补齐：${effective.bankInfoMocked ? '是' : '否'}`,
  ].join('；')
  const paymentUsage = [
    `付款方式：${paymentMethodText(effective.paymentMethod)}`,
    `付款银行：${effective.paymentBankName || '-'}`,
    `付款账号：${effective.paymentAccount || '-'}`,
    `账户名称：${effective.paymentAccountName || '-'}`,
    `来自企业默认账户：${effective.companyAccount ? '是' : '否'}`,
  ].join('；')
  const supplierPassed = Boolean(effective.supplierName)
    && Boolean(effective.supplierBankName)
    && Boolean(effective.supplierBankAccount)
    && Boolean(effective.supplierBankAccountName)
  const paymentAccountPassed = Boolean(effective.paymentMethod)
    && Boolean(effective.paymentAccount)
    && Boolean(effective.paymentAccountName)
    && Boolean(effective.paymentBankName)
  const items = [
    buildCheckItem('sourcePrepare', '付款单预备来源检查', Boolean(record.sourcePaymentPrepareNo) && SOURCE_READY_STATUSES.includes(sourcePrepare?.paymentPrepareStatus || ''), '来源付款单预备不存在，或状态不是 ready / checked。', 'error', '返回正式付款单预备列表，确认来源单据仍为 ready / checked 且未取消或关闭。'),
    buildCheckItem('supplier', '供应商检查', supplierPassed, supplierMissingReasons || '供应商名称、开户行、收款账号或账户名称不完整。', 'error', supplierUsage),
    buildCheckItem('amount', '金额检查', record.draftPayAmount > 0 && record.draftPayAmount <= record.unpaidAmount && record.confirmedPayAmount >= 0 && record.confirmedPayAmount <= record.unpaidAmount, '草稿付款金额或确认付款金额为空，或超过未付款金额。', 'error', '返回正式付款单预备或应付账款草稿核对金额，确保确认付款金额大于 0 且不超过未付款金额。'),
    buildCheckItem('paymentAccount', '付款账户检查', paymentAccountPassed, paymentMissingReasons || '付款方式、付款账号、付款账户名称或付款银行不完整。', 'error', paymentUsage),
    buildCheckItem('duplicatePayment', '防重复付款检查', !duplicate, '同一付款单预备或供应商付款草稿已有未关闭付款单草稿。', 'error', '查看已存在的正式付款单草稿；如需重做，请先取消或关闭未关闭记录。'),
    buildCheckItem('financeBoundary', '财务边界检查', record.bankPaymentStatus === 'notPaid' && record.voucherStatus === 'notGenerated', '本轮不得生成凭证、写总账或连接银行。', 'warning', '本轮只做付款执行前确认，不真实付款、不生成银行付款、不生成财务凭证、不写总账。'),
  ]
  if (effective.bankInfoMocked && supplierPassed) {
    items.splice(2, 0, buildCheckItem('supplierMockBankInfo', '供应商模拟银行信息提示', true, '供应商银行信息为系统自动补齐模拟数据，仅用于流程验证，后续请维护真实资料。', 'info', '后续在供应商档案维护真实开户行、账号和账户名称。'))
  }
  const hasError = items.some((item) => !item.passed && item.severity === 'error')
  const hasWarning = items.some((item) => !item.passed && item.severity === 'warning')
  return {
    executionCheckStatus: hasError ? 'blocked' : (hasWarning ? 'warning' : 'passed'),
    executionCheckResult: hasError ? '付款执行确认检查存在阻断项。' : (hasWarning ? '付款执行确认检查存在提示项，可继续处理。' : '付款执行确认检查通过。'),
    executionCheckItems: items,
  }
}

function buildLinesFromPaymentPrepare(prepare = {}) {
  return (prepare.lines || []).map((line, index) => normalizeLine({
    ...line,
    lineNo: index + 1,
    sourcePaymentPrepareLineId: line.id,
    draftPayAmount: line.preparePayAmount,
    confirmedPayAmount: line.preparePayAmount,
  }, index))
}

export function createPaymentOrderDraftFromPaymentPrepare(paymentPrepareId) {
  const prepare = getPaymentOrderPrepareById(paymentPrepareId)
  const reason = sourceRejectReason(prepare, true)
  if (reason) return { success: false, error: reason }
  const effective = effectivePaymentDraftFields(prepare, prepare)
  const draft = paymentOrderDraft({
    sourcePaymentPrepareId: prepare.id,
    sourcePaymentPrepareNo: prepare.paymentPrepareNo,
    sourcePaymentDraftId: prepare.sourcePaymentDraftId,
    sourcePaymentDraftNo: prepare.sourcePaymentDraftNo,
    sourceApDraftNo: prepare.sourceApDraftNo,
    sourceInvoicePrepareNo: prepare.sourceInvoicePrepareNo,
    sourcePayableCheckNo: prepare.sourcePayableCheckNo,
    sourcePayablePrepareNo: prepare.sourcePayablePrepareNo,
    supplierId: effective.supplierId || prepare.supplierId,
    supplierName: effective.supplierName || prepare.supplierName,
    sourcePurchaseOrderNo: prepare.sourcePurchaseOrderNo,
    sourceReceiveNo: prepare.sourceReceiveNo,
    sourceInspectionNo: prepare.sourceInspectionNo,
    sourceInventoryTransactionNos: prepare.sourceInventoryTransactionNos || [],
    rootRequestNo: prepare.rootRequestNo,
    expectedPayDate: prepare.expectedPayDate,
    totalPayableAmount: prepare.totalPayableAmount,
    paidAmount: prepare.paidAmount,
    unpaidAmount: prepare.unpaidAmount,
    applyPayAmount: prepare.applyPayAmount,
    approvedPayAmount: prepare.approvedPayAmount,
    draftPayAmount: prepare.preparePayAmount,
    confirmedPayAmount: prepare.preparePayAmount,
    paymentMethod: effective.paymentMethod || prepare.paymentMethod,
    paymentAccount: effective.paymentAccount || prepare.paymentAccount,
    paymentAccountName: effective.paymentAccountName || prepare.paymentAccountName,
    paymentBankName: effective.paymentBankName || prepare.paymentBankName,
    supplierBankName: effective.supplierBankName || prepare.supplierBankName,
    supplierBankAccount: effective.supplierBankAccount || prepare.supplierBankAccount,
    supplierBankAccountName: effective.supplierBankAccountName || prepare.supplierBankAccountName,
    bankInfoMocked: effective.bankInfoMocked || prepare.bankInfoMocked,
    bankInfoMockedAt: effective.bankInfoMockedAt || prepare.bankInfoMockedAt,
    bankInfoMockRemark: effective.bankInfoMockRemark || prepare.bankInfoMockRemark,
    remark: '由正式付款单预备生成，仅做付款执行确认；本轮不真实付款，不生成银行付款或财务凭证。',
    lines: buildLinesFromPaymentPrepare(prepare),
  })
  const check = runPaymentExecutionCheck(draft)
  Object.assign(draft, check)
  state.paymentOrderDrafts.unshift(draft)
  persist()
  writePaymentOrderDraftLog('从正式付款单预备生成正式付款单草稿', {
    sourceNo: prepare.paymentPrepareNo,
    targetId: draft.id,
    targetNo: draft.paymentOrderDraftNo,
    result: draft.draftPayAmount,
  })
  if (check.executionCheckStatus === 'blocked') writePaymentOrderDraftLog('付款确认检查阻断', { sourceNo: prepare.paymentPrepareNo, targetId: draft.id, targetNo: draft.paymentOrderDraftNo, result: check.executionCheckResult })
  return { success: true, paymentOrderDraftId: draft.id, paymentOrderDraftNo: draft.paymentOrderDraftNo, paymentOrderDraft: clone(draft) }
}

function batchResult(ids = [], handler, label, noGetter = (id) => id) {
  const result = {
    total: ids.length,
    successCount: 0,
    alreadyDoneCount: 0,
    failedCount: 0,
    successItems: [],
    alreadyDoneItems: [],
    failedItems: [],
    failedReason: [],
  }
  ids.forEach((id) => {
    const no = noGetter(id)
    const outcome = handler(id)
    if (outcome?.success) {
      if (outcome.alreadyDone) {
        const reason = outcome.message || '该记录已是目标状态，无需重复处理。'
        result.alreadyDoneCount += 1
        result.alreadyDoneItems.push({ id, no, reason })
        return
      }
      result.successCount += 1
      result.successItems.push({ id, no })
      return
    }
    const reason = outcome?.error || '当前记录不满足批量操作条件。'
    result.failedCount += 1
    result.failedItems.push({ id, no, reason })
    result.failedReason.push(`${no}：${reason}`)
  })
  writePaymentOrderDraftLog(label, { targetType: 'batch', targetId: label, result: `成功 ${result.successCount} 条，已达成 ${result.alreadyDoneCount} 条，失败 ${result.failedCount} 条；${result.failedReason.join('；')}` })
  if (result.alreadyDoneCount) {
    writePaymentOrderDraftLog('批量已达成跳过', {
      targetType: 'batch',
      targetId: label,
      result: result.alreadyDoneItems.map((item) => `${item.no}：${item.reason}`).join('；'),
    })
  }
  if (result.failedCount) writePaymentOrderDraftLog('批量失败原因', { targetType: 'batch', targetId: label, result: result.failedReason.join('；') })
  return result
}

export function batchCreatePaymentOrderDraftsFromPaymentPrepares(ids = []) {
  return batchResult(ids, createPaymentOrderDraftFromPaymentPrepare, '批量生成正式付款单草稿', (id) => getPaymentOrderPrepareById(id)?.paymentPrepareNo || id)
}

export function updatePaymentOrderDraft(id, patch = {}) {
  const current = byId(state.paymentOrderDrafts, id)
  if (!current || CLOSED_DRAFT_STATUSES.includes(current.paymentOrderStatus) || current.paymentOrderStatus === 'paymentReady') return { success: false, error: '当前正式付款单草稿不可修改。' }
  Object.assign(current, paymentOrderDraft({ ...current, ...patch, id: current.id, updatedAt: nowText() }))
  persist()
  writePaymentOrderDraftLog('更新正式付款单草稿', { targetId: current.id, targetNo: current.paymentOrderDraftNo })
  return { success: true, paymentOrderDraft: clone(current) }
}

function applyStatus(id, status, action, patch = {}) {
  const current = byId(state.paymentOrderDrafts, id)
  if (!current) return { success: false, error: '未找到正式付款单草稿。' }
  if (CLOSED_DRAFT_STATUSES.includes(current.paymentOrderStatus)) return { success: false, error: '已取消或已关闭的付款单草稿不能继续流转。' }
  Object.assign(current, patch, { paymentOrderStatus: status, updatedAt: nowText() })
  if (status === 'confirmed') {
    current.paymentConfirmed = true
    current.paymentConfirmedAt = current.paymentConfirmedAt || nowText()
    current.paymentConfirmedBy = current.paymentConfirmedBy || '系统演示用户'
    current.confirmDate = current.confirmDate || today()
  }
  if (status === 'paymentReady') {
    current.bankPaymentStatus = 'readyForBankPayment'
    current.voucherStatus = 'voucherReady'
  }
  persist()
  writePaymentOrderDraftLog(action, { sourceNo: current.sourcePaymentPrepareNo, targetId: current.id, targetNo: current.paymentOrderDraftNo })
  return { success: true, paymentOrderDraft: clone(current) }
}

export function markPaymentOrderDraftChecking(id) {
  const check = runPaymentExecutionCheck(id)
  const status = check.executionCheckStatus === 'blocked' ? 'checking' : 'checking'
  const outcome = applyStatus(id, status, '执行付款确认检查', check)
  if (check.executionCheckStatus === 'blocked') writePaymentOrderDraftLog('付款确认检查阻断', { targetId: id, result: check.executionCheckResult })
  return outcome
}

export function markPaymentExecutionConfirmed(id) {
  const current = byId(state.paymentOrderDrafts, id)
  if (!current) return { success: false, error: '未找到正式付款单草稿。' }
  if (!['draft', 'checking'].includes(current.paymentOrderStatus)) return { success: false, error: '只有草稿或确认中的付款单草稿可确认付款执行。' }
  const check = runPaymentExecutionCheck(current)
  if (check.executionCheckStatus === 'blocked') return applyStatus(id, 'checking', '付款确认检查阻断', check)
  return applyStatus(id, 'confirmed', '确认付款执行', check)
}

export function markPaymentOrderPaymentReady(id) {
  const current = byId(state.paymentOrderDrafts, id)
  if (!current) return { success: false, error: '未找到正式付款单草稿。' }
  if (current.paymentOrderStatus === 'paymentReady') {
    const message = '该记录已是可进入真实付款，无需重复标记。'
    writePaymentOrderDraftLog('重复标记可进入真实付款已达成跳过', {
      sourceNo: current.sourcePaymentPrepareNo,
      targetId: current.id,
      targetNo: current.paymentOrderDraftNo,
      result: message,
    })
    return { success: true, alreadyDone: true, message, paymentOrderDraft: clone(current) }
  }
  if (current.paymentOrderStatus !== 'confirmed') return { success: false, error: '必须先确认付款执行，才能标记可进入真实付款。' }
  const check = runPaymentExecutionCheck(current)
  if (check.executionCheckStatus === 'blocked') return { success: false, error: '付款执行确认检查未通过，不能标记可进入真实付款。' }
  return applyStatus(id, 'paymentReady', '标记可进入真实付款', check)
}

export function cancelPaymentOrderDraft(id) {
  const current = byId(state.paymentOrderDrafts, id)
  if (current && !['draft', 'checking'].includes(current.paymentOrderStatus)) return { success: false, error: '当前状态不能取消；已确认或可付款的草稿不能取消。' }
  return applyStatus(id, 'cancelled', '取消付款单草稿')
}

export function batchRunPaymentExecutionChecks(ids = []) {
  return batchResult(ids, markPaymentOrderDraftChecking, '批量执行付款确认检查', (id) => byId(state.paymentOrderDrafts, id)?.paymentOrderDraftNo || id)
}

export function batchMarkPaymentExecutionConfirmed(ids = []) {
  return batchResult(ids, markPaymentExecutionConfirmed, '批量确认付款执行', (id) => byId(state.paymentOrderDrafts, id)?.paymentOrderDraftNo || id)
}

export function batchMarkPaymentOrderPaymentReady(ids = []) {
  return batchResult(ids, markPaymentOrderPaymentReady, '批量标记可进入真实付款', (id) => byId(state.paymentOrderDrafts, id)?.paymentOrderDraftNo || id)
}

export function batchCancelPaymentOrderDrafts(ids = []) {
  return batchResult(ids, cancelPaymentOrderDraft, '批量取消付款单草稿', (id) => byId(state.paymentOrderDrafts, id)?.paymentOrderDraftNo || id)
}
