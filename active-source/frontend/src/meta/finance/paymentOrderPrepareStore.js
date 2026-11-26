import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  buildPaymentPrepareSupplierBankFields,
  findSupplierProfileForPayment,
  getDefaultCompanyBankAccount,
  normalizePaymentMethod,
  writeBusinessPartnerLog,
} from '../foundation/businessPartnerStore.js'
import {
  getSupplierPaymentDraftById,
  listSupplierPaymentDrafts,
  markPaymentDraftPrepareGenerated,
} from './supplierPaymentDraftStore.js'

const STORAGE_KEY = 'payment-order-prepare-state-v1'
const SOURCE_READY_STATUSES = ['approved', 'paymentReady']
const ACTIVE_PREPARE_STATUSES = ['draft', 'checking', 'checked', 'ready', 'blocked']

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
  return { paymentOrderPrepares: [] }
}

function byId(collection, id) {
  return (collection || []).find((item) => String(item.id) === String(id)) || null
}

function normalizeLine(line = {}, index = 0) {
  const payableAmount = roundAmount(line.payableAmount)
  const paidAmount = roundAmount(line.paidAmount ?? 0)
  const unpaidAmount = roundAmount(line.unpaidAmount ?? Math.max(payableAmount - paidAmount, 0))
  const applyPayAmount = roundAmount(line.applyPayAmount ?? unpaidAmount)
  const approvedPayAmount = roundAmount(line.approvedPayAmount ?? applyPayAmount)
  const preparePayAmount = roundAmount(line.preparePayAmount ?? approvedPayAmount)
  return {
    id: line.id || createId('popl'),
    lineNo: line.lineNo || index + 1,
    sourcePaymentDraftLineId: line.sourcePaymentDraftLineId || line.id || '',
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
    preparePayAmount: Math.min(Math.max(preparePayAmount, 0), unpaidAmount),
    sourcePurchaseOrderNo: line.sourcePurchaseOrderNo || '',
    sourceReceiveNo: line.sourceReceiveNo || '',
    sourceInspectionNo: line.sourceInspectionNo || '',
    sourceInventoryTransactionNo: line.sourceInventoryTransactionNo || '',
    rootRequestNo: line.rootRequestNo || '',
    remark: line.remark || '',
  }
}

function paymentOrderPrepare(payload = {}) {
  const stamp = nowText()
  const lines = (payload.lines || []).map(normalizeLine)
  const totalPayableAmount = roundAmount(payload.totalPayableAmount)
  const paidAmount = roundAmount(payload.paidAmount ?? 0)
  const unpaidAmount = roundAmount(payload.unpaidAmount ?? Math.max(totalPayableAmount - paidAmount, 0))
  const applyPayAmount = roundAmount(payload.applyPayAmount ?? unpaidAmount)
  const approvedPayAmount = roundAmount(payload.approvedPayAmount ?? applyPayAmount)
  const preparePayAmount = roundAmount(payload.preparePayAmount ?? approvedPayAmount)
  const preCheckItems = payload.preCheckItems || []
  return {
    id: payload.id || createId('pop'),
    paymentPrepareNo: payload.paymentPrepareNo || createNo('POP'),
    sourcePaymentDraftId: payload.sourcePaymentDraftId || '',
    sourcePaymentDraftNo: payload.sourcePaymentDraftNo || '',
    paymentDraftStatus: payload.paymentDraftStatus || '',
    sourceApDraftNo: payload.sourceApDraftNo || '',
    sourceInvoicePrepareNo: payload.sourceInvoicePrepareNo || '',
    sourcePayableCheckNo: payload.sourcePayableCheckNo || '',
    sourcePayablePrepareNo: payload.sourcePayablePrepareNo || '',
    supplierId: payload.supplierId || '',
    supplierName: payload.supplierName || '',
    sourcePurchaseOrderNo: payload.sourcePurchaseOrderNo || '',
    sourceReceiveNo: payload.sourceReceiveNo || '',
    sourceInspectionNo: payload.sourceInspectionNo || '',
    sourceInventoryTransactionNos: payload.sourceInventoryTransactionNos || [],
    rootRequestNo: payload.rootRequestNo || '',
    paymentPrepareStatus: payload.paymentPrepareStatus || 'draft',
    prepareDate: payload.prepareDate || today(),
    expectedPayDate: payload.expectedPayDate || payload.dueDate || '',
    dueDate: payload.dueDate || payload.expectedPayDate || '',
    totalPayableAmount,
    paidAmount,
    unpaidAmount,
    applyPayAmount,
    approvedPayAmount,
    preparePayAmount: Math.min(Math.max(preparePayAmount, 0), unpaidAmount),
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
    preCheckStatus: payload.preCheckStatus || 'notChecked',
    preCheckResult: payload.preCheckResult || '',
    preCheckItems,
    supplierInfoChecked: payload.supplierInfoChecked ?? false,
    amountChecked: payload.amountChecked ?? false,
    invoiceChecked: payload.invoiceChecked ?? false,
    apChecked: payload.apChecked ?? false,
    approvalChecked: payload.approvalChecked ?? false,
    duplicatePaymentChecked: payload.duplicatePaymentChecked ?? false,
    bankInfoChecked: payload.bankInfoChecked ?? false,
    riskLevel: payload.riskLevel || riskLevelFromItems(preCheckItems),
    riskReason: payload.riskReason || riskReasonFromItems(preCheckItems),
    paymentReady: payload.paymentReady ?? false,
    realPaymentStatus: payload.realPaymentStatus || 'notPaid',
    voucherStatus: payload.voucherStatus || 'notGenerated',
    remark: payload.remark || '',
    lines,
    createdAt: payload.createdAt || stamp,
    updatedAt: payload.updatedAt || stamp,
  }
}

function normalizeState(raw = {}) {
  return { paymentOrderPrepares: (raw.paymentOrderPrepares || []).map(paymentOrderPrepare) }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[PAYMENT ORDER PREPARE STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function riskLevelFromItems(items = []) {
  if (items.some((item) => item.severity === 'error' && !item.passed)) return 'high'
  if (items.some((item) => item.severity === 'warning' && !item.passed)) return 'medium'
  return items.length ? 'low' : 'none'
}

function riskReasonFromItems(items = []) {
  return items.filter((item) => !item.passed).map((item) => item.message).join('；')
}

function buildCheckItem(key, label, passed, message, severity = 'error', suggestion = '请按失败原因补正后重新执行付款前检查。') {
  return {
    key,
    label,
    passed: Boolean(passed),
    message: passed ? '检查通过。' : message,
    severity: passed ? 'info' : severity,
    suggestion: passed ? (suggestion || '无需处理。') : suggestion,
  }
}

function paymentMethodText(method) {
  const normalized = normalizePaymentMethod(method)
  return { bankTransfer: '银行转账', cash: '现金', cheque: '支票', acceptance: '承兑', other: '其他' }[normalized] || normalized || '-'
}

function hasActivePaymentOrderDraftForPrepare(record = {}) {
  try {
    const raw = localStorage.getItem('payment-order-draft-state-v1')
    const drafts = raw ? JSON.parse(raw).paymentOrderDrafts || [] : []
    return drafts.some((draft) => (
      String(draft.sourcePaymentPrepareId) === String(record.id || '')
      && ['draft', 'checking', 'confirmed', 'paymentReady'].includes(draft.paymentOrderStatus)
    ))
  } catch (error) {
    console.warn('[PAYMENT ORDER PREPARE STORE] skip draft duplicate check', error)
    return false
  }
}

export function writePaymentPrepareLog(action, payload = {}) {
  addOperationLog({
    module: '正式付款单预备',
    action,
    targetType: payload.targetType || 'paymentOrderPrepare',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源单据：${payload.sourceNo || '-'}`,
      `目标单据：${payload.targetNo || '-'}`,
      `结果：${payload.result || '成功'}`,
    ].join('；'),
  })
}

export function getPaymentOrderPrepareState() {
  return clone(state)
}

export function savePaymentOrderPrepareState(nextState) {
  state = normalizeState(nextState)
  persist()
  writePaymentPrepareLog('保存正式付款单预备状态', { targetType: 'paymentOrderPrepareState', targetId: 'state' })
  return getPaymentOrderPrepareState()
}

export function resetPaymentOrderPrepareState() {
  state = defaultState()
  persist()
  writePaymentPrepareLog('恢复正式付款单预备演示数据', { targetType: 'paymentOrderPrepareState', targetId: 'demo' })
  return getPaymentOrderPrepareState()
}

export function listPaymentOrderPrepares() {
  return clone(state.paymentOrderPrepares)
}

export function getPaymentOrderPrepareById(id) {
  return clone(byId(state.paymentOrderPrepares, id))
}

export function isPaymentPrepareGenerated(paymentDraftOrId) {
  const draft = typeof paymentDraftOrId === 'object' ? paymentDraftOrId : getSupplierPaymentDraftById(paymentDraftOrId)
  if (!draft?.id) return false
  return state.paymentOrderPrepares.some((prepare) => (
    (String(prepare.sourcePaymentDraftId) === String(draft.id) || String(prepare.sourceApDraftNo) === String(draft.sourceApDraftNo || ''))
    && ACTIVE_PREPARE_STATUSES.includes(prepare.paymentPrepareStatus)
  ))
}

function sourceRejectReason(draft = {}) {
  if (!draft?.id) return '未找到供应商付款草稿。'
  if (isPaymentPrepareGenerated(draft)) {
    writePaymentPrepareLog('防重复生成拦截', {
      sourceNo: draft.paymentDraftNo,
      result: '该供应商付款草稿已生成正式付款单预备，不能重复生成。',
    })
    return '该供应商付款草稿已生成正式付款单预备，不能重复生成。'
  }
  if (!SOURCE_READY_STATUSES.includes(draft.paymentDraftStatus)) return '只有 approved 或 paymentReady 状态的供应商付款草稿可生成正式付款单预备。'
  if (roundAmount(draft.unpaidAmount) <= 0) return '未付款金额为 0，不能生成付款单预备。'
  if (roundAmount(draft.applyPayAmount) <= 0) return '申请付款金额为 0，不能生成付款单预备。'
  if (roundAmount(draft.applyPayAmount) > roundAmount(draft.unpaidAmount)) return '申请付款金额不能大于未付款金额。'
  return ''
}

export function getPaymentPrepareSourcesFromPaymentDrafts() {
  return listSupplierPaymentDrafts().map((draft) => {
    const existed = state.paymentOrderPrepares.find((prepare) => (
      String(prepare.sourcePaymentDraftId) === String(draft.id)
      && ACTIVE_PREPARE_STATUSES.includes(prepare.paymentPrepareStatus)
    ))
    const target = state.paymentOrderPrepares.find((prepare) => (
      String(prepare.id) === String(draft.targetPaymentPrepareId || '')
      || String(prepare.paymentPrepareNo) === String(draft.targetPaymentPrepareNo || '')
    ))
    const hasHistoricalWriteBack = (draft.paymentPrepareGenerated || draft.targetPaymentPrepareId || draft.targetPaymentPrepareNo) && !target
    const generated = Boolean(existed || hasHistoricalWriteBack || (target && ACTIVE_PREPARE_STATUSES.includes(target.paymentPrepareStatus)))
    const reason = sourceRejectReason(draft)
    return {
      ...draft,
      paymentPrepareGenerated: generated,
      paymentPrepareGeneratedText: generated ? '已生成' : '未生成',
      targetPaymentPrepareId: draft.targetPaymentPrepareId || existed?.id || '',
      targetPaymentPrepareNo: draft.targetPaymentPrepareNo || existed?.paymentPrepareNo || '',
      canCreatePaymentPrepare: !reason,
      sourceRejectReason: reason,
    }
  })
}

export function runPaymentPreCheck(recordOrId) {
  const record = typeof recordOrId === 'object'
    ? (recordOrId.id ? (byId(state.paymentOrderPrepares, recordOrId.id) || recordOrId) : recordOrId)
    : byId(state.paymentOrderPrepares, recordOrId)
  if (!record?.id && !record?.paymentDraftNo) return { preCheckStatus: 'blocked', preCheckResult: '未找到付款预备数据。', preCheckItems: [] }
  const sourceDraft = (record.sourcePaymentDraftId ? getSupplierPaymentDraftById(record.sourcePaymentDraftId) : null) || record
  const supplierProfile = findSupplierProfileForPayment(record)
  const companyAccount = getDefaultCompanyBankAccount()
  const supplierBankFields = supplierProfile ? buildPaymentPrepareSupplierBankFields(supplierProfile) : {}
  const effectiveSupplierBankName = record.supplierBankName || supplierBankFields.supplierBankName || ''
  const effectiveSupplierBankAccount = record.supplierBankAccount || supplierBankFields.supplierBankAccount || ''
  const effectiveSupplierBankAccountName = record.supplierBankAccountName || supplierBankFields.supplierBankAccountName || ''
  const effectivePaymentMethod = normalizePaymentMethod(record.paymentMethod || supplierBankFields.paymentMethod || 'bankTransfer')
  const effectivePaymentAccount = record.paymentAccount || companyAccount?.bankAccount || ''
  const effectivePaymentAccountName = record.paymentAccountName || companyAccount?.accountName || ''
  const effectivePaymentBankName = record.paymentBankName || companyAccount?.bankName || ''
  const autoPatch = {}
  if (!record.supplierBankName && effectiveSupplierBankName) autoPatch.supplierBankName = effectiveSupplierBankName
  if (!record.supplierBankAccount && effectiveSupplierBankAccount) autoPatch.supplierBankAccount = effectiveSupplierBankAccount
  if (!record.supplierBankAccountName && effectiveSupplierBankAccountName) autoPatch.supplierBankAccountName = effectiveSupplierBankAccountName
  if (!record.paymentMethod && effectivePaymentMethod) autoPatch.paymentMethod = effectivePaymentMethod
  if (!record.paymentAccount && effectivePaymentAccount) autoPatch.paymentAccount = effectivePaymentAccount
  if (!record.paymentAccountName && effectivePaymentAccountName) autoPatch.paymentAccountName = effectivePaymentAccountName
  if (!record.paymentBankName && effectivePaymentBankName) autoPatch.paymentBankName = effectivePaymentBankName
  if (supplierProfile?.bankInfoMocked && !record.bankInfoMocked) {
    autoPatch.bankInfoMocked = true
    autoPatch.bankInfoMockedAt = supplierProfile.bankInfoMockedAt || nowText()
    autoPatch.bankInfoMockRemark = supplierProfile.bankInfoMockRemark || '供应商银行信息为系统自动补齐模拟数据，仅用于流程验证。'
  }
  if (record.id && Object.keys(autoPatch).length) {
    Object.assign(record, paymentOrderPrepare({ ...record, ...autoPatch, id: record.id, createdAt: record.createdAt, updatedAt: nowText() }))
    persist()
    if (autoPatch.supplierBankName || autoPatch.supplierBankAccount || autoPatch.supplierBankAccountName) writePaymentPrepareLog('付款前检查自动补齐供应商银行信息', { targetId: record.id, targetNo: record.paymentPrepareNo, result: supplierProfile?.supplierName || record.supplierName })
    if (autoPatch.paymentAccount || autoPatch.paymentAccountName || autoPatch.paymentBankName) writePaymentPrepareLog('付款前检查自动补齐企业付款账户', { targetId: record.id, targetNo: record.paymentPrepareNo, result: companyAccount?.accountCode || companyAccount?.bankName || '企业默认账户' })
  }
  const duplicate = state.paymentOrderPrepares.some((prepare) => (
    prepare.id !== record.id
    && ACTIVE_PREPARE_STATUSES.includes(prepare.paymentPrepareStatus)
    && (String(prepare.sourcePaymentDraftId) === String(record.sourcePaymentDraftId) || String(prepare.sourceApDraftNo) === String(record.sourceApDraftNo))
  ))
  const hasDraftDuplicate = hasActivePaymentOrderDraftForPrepare(record)
  const supplierBasePassed = Boolean(record.supplierName) && Boolean(effectiveSupplierBankName) && Boolean(effectiveSupplierBankAccount)
  const supplierAccountNamePassed = Boolean(effectiveSupplierBankAccountName)
  const paymentAccountPassed = Boolean(effectivePaymentMethod) && Boolean(effectivePaymentAccount) && Boolean(effectivePaymentAccountName) && Boolean(effectivePaymentBankName)
  const amountPassed = record.applyPayAmount > 0 && record.approvedPayAmount > 0 && record.preparePayAmount > 0 && record.preparePayAmount <= record.unpaidAmount
  const invoicePassed = Boolean(record.sourceInvoicePrepareNo) || Boolean(record.sourceApDraftNo)
  const apPassed = Boolean(record.sourceApDraftNo) && record.unpaidAmount > 0
  const approvalPassed = ['approved', 'paymentReady'].includes(sourceDraft?.paymentDraftStatus || record.paymentDraftStatus)
  const supplierMocked = Boolean(supplierProfile?.bankInfoMocked || record.bankInfoMocked)
  if (supplierProfile) {
    writeBusinessPartnerLog('付款前检查读取供应商档案', { targetType: 'paymentOrderPrepare', targetId: record.id, targetNo: record.paymentPrepareNo, detail: supplierProfile.supplierName })
  }
  if (supplierMocked) {
    writeBusinessPartnerLog('付款前检查发现供应商银行信息为模拟数据', { targetType: 'paymentOrderPrepare', targetId: record.id, targetNo: record.paymentPrepareNo, detail: supplierProfile?.supplierName || record.supplierName })
  }
  if (!supplierProfile) {
    writeBusinessPartnerLog('付款前检查未找到供应商档案', { targetType: 'paymentOrderPrepare', targetId: record.id, targetNo: record.paymentPrepareNo, detail: record.supplierName || record.supplierId || '-' })
  }
  const supplierMissingReasons = []
  if (!record.supplierName) supplierMissingReasons.push('缺少供应商名称')
  if (!supplierProfile) supplierMissingReasons.push('未找到供应商档案，请先归集或维护供应商档案')
  if (!effectiveSupplierBankName) supplierMissingReasons.push('供应商开户行缺失')
  if (!effectiveSupplierBankAccount) supplierMissingReasons.push('供应商银行账号缺失')
  if (!effectiveSupplierBankAccountName) supplierMissingReasons.push('供应商账户名称缺失')
  if (!effectivePaymentMethod) supplierMissingReasons.push('默认付款方式缺失')
  const paymentMissingReasons = []
  if (!effectivePaymentMethod) paymentMissingReasons.push('默认付款方式缺失')
  if (!effectivePaymentBankName) paymentMissingReasons.push('企业付款银行缺失')
  if (!effectivePaymentAccount) paymentMissingReasons.push('企业付款账号缺失')
  if (!effectivePaymentAccountName) paymentMissingReasons.push('企业付款账户名称缺失')
  const supplierUsage = [
    `供应商名称：${record.supplierName || '-'}`,
    `供应商开户行：${effectiveSupplierBankName || '-'}`,
    `供应商银行账号：${effectiveSupplierBankAccount || '-'}`,
    `供应商账户名称：${effectiveSupplierBankAccountName || '-'}`,
    `来自供应商档案：${supplierProfile ? '是' : '否'}`,
    `模拟补齐：${supplierMocked ? '是' : '否'}`,
  ].join('；')
  const paymentUsage = [
    `付款方式：${paymentMethodText(effectivePaymentMethod)}`,
    `付款银行：${effectivePaymentBankName || '-'}`,
    `付款账号：${effectivePaymentAccount || '-'}`,
    `付款账户名称：${effectivePaymentAccountName || '-'}`,
    `来自企业默认账户：${companyAccount ? '是' : '否'}`,
  ].join('；')
  const items = [
    buildCheckItem('supplierInfo', '供应商信息检查', supplierBasePassed, supplierMissingReasons.join('；') || '供应商信息不完整。', 'error', `${supplierUsage}。请从供应商档案带出银行信息，或维护供应商档案后重新检查。`),
    buildCheckItem('supplierAccountName', '供应商账户名称检查', supplierAccountNamePassed, '供应商账户名称缺失。', 'warning', `${supplierUsage}。请补充供应商账户名称后重新检查。`),
    buildCheckItem('paymentAccount', '付款账户检查', paymentAccountPassed, paymentMissingReasons.join('；') || '付款账户缺失。', 'error', `${paymentUsage}。请从企业默认账户带出付款账户，或维护企业银行账户后重新检查。`),
    buildCheckItem('amount', '金额检查', amountPassed, '付款金额无效，请确认申请付款金额不能为 0 且不能大于未付款金额。', 'error', '在付款信息补正区调整批准付款金额和预备付款金额，确保大于 0 且不超过未付款金额。'),
    buildCheckItem('invoice', '发票检查', invoicePassed, '来源发票信息缺失，请检查发票预备是否已匹配。', 'warning', '返回发票预备或应付账款草稿确认来源链路，再重新检查。'),
    buildCheckItem('accountPayable', '应付账款检查', apPassed, '来源应付账款草稿状态不满足付款条件。', 'error', '返回应付账款草稿确认其已进入 confirmed / paymentPending / 付款草稿链路。'),
    buildCheckItem('approval', '付款申请审批检查', approvalPassed, '付款申请尚未审批通过，请先审批付款申请。', 'error', '返回供应商付款草稿完成审批或标记可付款后重新检查。'),
    buildCheckItem('duplicatePayment', '防重复付款检查', !duplicate && !hasDraftDuplicate, '已存在未关闭的付款预备或付款草稿，不能重复生成。', 'error', '请查看已存在的付款预备/付款单草稿；如需重做，请先取消未关闭记录。'),
    buildCheckItem('financeBoundary', '财务边界检查', true, '本轮不得真实付款、不得生成银行付款、不得生成财务凭证。', 'info', '无需处理；后续真实付款模块再处理银行和凭证。'),
  ]
  if (supplierMocked && supplierBasePassed && supplierAccountNamePassed) {
    items.splice(2, 0, buildCheckItem('supplierMockBankInfo', '供应商模拟银行信息提示', true, '供应商银行信息为系统自动补齐模拟数据，仅用于流程验证，请后续维护真实资料。', 'info', '后续在供应商档案中维护真实开户行、账号和账户名称。'))
  }
  if (!supplierProfile) {
    items.splice(2, 0, buildCheckItem('supplierProfile', '供应商档案检查', supplierBasePassed, '未找到供应商档案，请先维护供应商档案或执行“归集历史供应商”。', supplierBasePassed ? 'warning' : 'error', '进入供应商档案页执行“归集历史供应商”或手工维护供应商档案。'))
  }
  const hasError = items.some((item) => !item.passed && item.severity === 'error')
  const hasWarning = items.some((item) => !item.passed && item.severity === 'warning')
  if (record.bankInfoMocked && supplierBasePassed && supplierAccountNamePassed) {
    writePaymentPrepareLog('模拟银行信息通过供应商收款账户检查', { targetId: record.id, targetNo: record.paymentPrepareNo })
  }
  if (record.bankInfoMocked && paymentAccountPassed) {
    writePaymentPrepareLog('模拟银行信息通过付款账户检查', { targetId: record.id, targetNo: record.paymentPrepareNo })
  }
  const itemPassed = (key) => Boolean(items.find((item) => item.key === key)?.passed)
  return {
    preCheckStatus: hasError ? 'blocked' : (hasWarning ? 'warning' : 'passed'),
    preCheckResult: hasError ? '付款前检查存在阻断项。' : (hasWarning ? '付款前检查存在提示项，可继续处理。' : '付款前检查通过。'),
    preCheckItems: items,
    supplierInfoChecked: itemPassed('supplierInfo'),
    amountChecked: itemPassed('amount'),
    invoiceChecked: itemPassed('invoice'),
    apChecked: itemPassed('accountPayable'),
    approvalChecked: itemPassed('approval'),
    duplicatePaymentChecked: itemPassed('duplicatePayment'),
    bankInfoChecked: itemPassed('paymentAccount'),
    riskLevel: riskLevelFromItems(items),
    riskReason: riskReasonFromItems(items),
  }
}

function buildLinesFromPaymentDraft(draft = {}) {
  return (draft.lines || []).map((line, index) => normalizeLine({
    ...line,
    lineNo: index + 1,
    sourcePaymentDraftLineId: line.id,
    approvedPayAmount: line.applyPayAmount,
    preparePayAmount: line.applyPayAmount,
  }, index))
}

export function createPaymentPrepareFromPaymentDraft(paymentDraftId) {
  const draft = getSupplierPaymentDraftById(paymentDraftId)
  const reason = sourceRejectReason(draft)
  if (reason) return { success: false, error: reason }
  const prepare = paymentOrderPrepare({
    sourcePaymentDraftId: draft.id,
    sourcePaymentDraftNo: draft.paymentDraftNo,
    paymentDraftStatus: draft.paymentDraftStatus,
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
    expectedPayDate: draft.expectedPayDate,
    dueDate: draft.dueDate,
    totalPayableAmount: draft.totalPayableAmount,
    paidAmount: draft.paidAmount,
    unpaidAmount: draft.unpaidAmount,
    applyPayAmount: draft.applyPayAmount,
    approvedPayAmount: draft.applyPayAmount,
    preparePayAmount: draft.applyPayAmount,
    paymentMethod: draft.paymentMethod,
    paymentAccount: draft.paymentAccount,
    supplierBankName: draft.supplierBankName,
    supplierBankAccount: draft.supplierBankAccount,
    remark: '由供应商付款草稿生成，仅做付款执行前检查和正式付款单预备，不真实付款，不生成银行付款或财务凭证。',
    lines: buildLinesFromPaymentDraft(draft),
  })
  const check = runPaymentPreCheck(prepare)
  Object.assign(prepare, check, { paymentPrepareStatus: check.preCheckStatus === 'blocked' ? 'blocked' : 'draft' })
  state.paymentOrderPrepares.unshift(prepare)
  persist()
  const writeBack = markPaymentDraftPrepareGenerated(draft.id, prepare)
  writePaymentPrepareLog('从供应商付款草稿生成正式付款单预备', {
    sourceNo: draft.paymentDraftNo,
    targetId: prepare.id,
    targetNo: prepare.paymentPrepareNo,
    result: prepare.preparePayAmount,
  })
  if (check.preCheckStatus === 'blocked') writePaymentPrepareLog('付款前检查阻断', { sourceNo: draft.paymentDraftNo, targetId: prepare.id, targetNo: prepare.paymentPrepareNo, result: check.preCheckResult })
  return { success: true, paymentPrepareId: prepare.id, paymentPrepareNo: prepare.paymentPrepareNo, paymentOrderPrepare: clone(prepare), writeBackSuccess: Boolean(writeBack?.success) }
}

function batchResult(ids = [], handler, label, noGetter = (id) => id) {
  const result = { total: ids.length, successCount: 0, failedCount: 0, successItems: [], failedItems: [], failedReason: [] }
  ids.forEach((id) => {
    const no = noGetter(id)
    const outcome = handler(id)
    if (outcome?.success) {
      result.successCount += 1
      result.successItems.push({ id, no })
      return
    }
    const reason = outcome?.error || '当前记录不满足批量操作条件。'
    result.failedCount += 1
    result.failedItems.push({ id, no, reason })
    result.failedReason.push(`${no}：${reason}`)
  })
  writePaymentPrepareLog(label, { targetType: 'batch', targetId: label, result: `成功 ${result.successCount} 条，失败 ${result.failedCount} 条；${result.failedReason.join('；')}` })
  if (result.failedCount) writePaymentPrepareLog('批量失败原因', { targetType: 'batch', targetId: label, result: result.failedReason.join('；') })
  return result
}

export function batchCreatePaymentPreparesFromPaymentDrafts(ids = []) {
  return batchResult(ids, createPaymentPrepareFromPaymentDraft, '批量生成正式付款单预备', (id) => getSupplierPaymentDraftById(id)?.paymentDraftNo || id)
}

export function updatePaymentPrepare(id, patch = {}) {
  const current = byId(state.paymentOrderPrepares, id)
  if (!current || ['cancelled', 'closed', 'ready'].includes(current.paymentPrepareStatus)) return { success: false, error: '当前付款单预备不可修改。' }
  Object.assign(current, paymentOrderPrepare({
    ...current,
    ...patch,
    id: current.id,
    preCheckStatus: 'pending',
    preCheckResult: '付款信息已修改，请重新执行付款前检查。',
    riskLevel: 'none',
    riskReason: '付款信息已修改，请重新执行付款前检查。',
    updatedAt: nowText(),
  }))
  persist()
  writePaymentPrepareLog('保存付款信息', { targetId: current.id, targetNo: current.paymentPrepareNo, result: '付款信息已修改，请重新执行付款前检查。' })
  return { success: true, paymentOrderPrepare: clone(current) }
}

function applyStatus(id, status, action, patch = {}) {
  const current = byId(state.paymentOrderPrepares, id)
  if (!current) return { success: false, error: '未找到正式付款单预备。' }
  if (['cancelled', 'closed'].includes(current.paymentPrepareStatus)) return { success: false, error: '已取消或已关闭的付款单预备不能继续流转。' }
  Object.assign(current, patch, { paymentPrepareStatus: status, updatedAt: nowText() })
  if (status === 'ready') {
    current.paymentReady = true
    current.realPaymentStatus = 'paymentPrepared'
  }
  persist()
  writePaymentPrepareLog(action, { sourceNo: current.sourcePaymentDraftNo, targetId: current.id, targetNo: current.paymentPrepareNo })
  return { success: true, paymentOrderPrepare: clone(current) }
}

export function markPaymentPrepareChecking(id) {
  const check = runPaymentPreCheck(id)
  const status = check.preCheckStatus === 'blocked' ? 'blocked' : (check.preCheckStatus === 'passed' ? 'checked' : 'checking')
  const outcome = applyStatus(id, status, '执行付款前检查', check)
  if (check.preCheckStatus === 'passed') writePaymentPrepareLog('付款前检查通过', { targetId: id, result: check.preCheckResult })
  if (check.preCheckStatus === 'warning') writePaymentPrepareLog('付款前检查警告', { targetId: id, result: check.preCheckResult })
  if (check.preCheckStatus === 'blocked') writePaymentPrepareLog('付款前检查阻断', { targetId: id, result: check.preCheckResult })
  return outcome
}

export function markPaymentPrepareChecked(id) {
  const current = byId(state.paymentOrderPrepares, id)
  if (!current) return { success: false, error: '未找到正式付款单预备。' }
  const check = runPaymentPreCheck(current)
  if (check.preCheckStatus === 'blocked') {
    writePaymentPrepareLog('阻断状态下拦截标记已检查', { targetId: id, targetNo: current.paymentPrepareNo, result: '付款前检查未通过，不能进入正式付款。' })
    return { success: false, error: '付款前检查未通过，请先补正问题并重新检查。' }
  }
  return applyStatus(id, 'checked', '标记已检查', check)
}

export function markPaymentPrepareReady(id) {
  const current = byId(state.paymentOrderPrepares, id)
  if (!current) return { success: false, error: '未找到正式付款单预备。' }
  const check = runPaymentPreCheck(current)
  if (check.preCheckStatus === 'blocked') {
    writePaymentPrepareLog('阻断状态下拦截标记可进入正式付款', { targetId: id, targetNo: current.paymentPrepareNo, result: '付款前检查未通过，不能进入正式付款。' })
    return { success: false, error: '付款前检查未通过，请先补正问题并重新检查。' }
  }
  if (!['checked', 'checking', 'draft'].includes(current.paymentPrepareStatus)) return { success: false, error: '当前状态不能标记可进入正式付款。' }
  return applyStatus(id, 'ready', '标记可进入正式付款', check)
}

export function markPaymentPrepareBlocked(id) {
  return applyStatus(id, 'blocked', '标记付款前检查阻断')
}

export function cancelPaymentPrepare(id) {
  const current = byId(state.paymentOrderPrepares, id)
  if (current && !['draft', 'checking', 'checked', 'blocked'].includes(current.paymentPrepareStatus)) return { success: false, error: '当前状态不能取消。' }
  return applyStatus(id, 'cancelled', '取消付款单预备')
}

export function batchRunPaymentPreChecks(ids = []) {
  return batchResult(ids, markPaymentPrepareChecking, '批量执行付款前检查', (id) => byId(state.paymentOrderPrepares, id)?.paymentPrepareNo || id)
}

export function batchMarkPaymentPrepareChecked(ids = []) {
  return batchResult(ids, (id) => {
    const current = byId(state.paymentOrderPrepares, id)
    if (current && (current.preCheckStatus === 'blocked' || current.riskLevel === 'high')) {
      writePaymentPrepareLog('批量操作跳过 blocked 记录', { targetId: id, targetNo: current.paymentPrepareNo, result: '付款前检查未通过，不能进入正式付款。' })
      return { success: false, error: '付款前检查未通过，不能进入正式付款。' }
    }
    return markPaymentPrepareChecked(id)
  }, '批量标记已检查', (id) => byId(state.paymentOrderPrepares, id)?.paymentPrepareNo || id)
}

export function batchMarkPaymentPrepareReady(ids = []) {
  return batchResult(ids, (id) => {
    const current = byId(state.paymentOrderPrepares, id)
    if (current && (current.preCheckStatus === 'blocked' || current.riskLevel === 'high')) {
      writePaymentPrepareLog('批量操作跳过 blocked 记录', { targetId: id, targetNo: current.paymentPrepareNo, result: '付款前检查未通过，不能进入正式付款。' })
      return { success: false, error: '付款前检查未通过，不能进入正式付款。' }
    }
    return markPaymentPrepareReady(id)
  }, '批量标记可进入正式付款', (id) => byId(state.paymentOrderPrepares, id)?.paymentPrepareNo || id)
}

export function batchCancelPaymentPrepares(ids = []) {
  return batchResult(ids, cancelPaymentPrepare, '批量取消付款单预备', (id) => byId(state.paymentOrderPrepares, id)?.paymentPrepareNo || id)
}
