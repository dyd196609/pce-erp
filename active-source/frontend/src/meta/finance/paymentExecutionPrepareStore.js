import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  getPaymentInstructionPrepareById,
  linkPaymentOrderPrepareExecutionPrepare,
  listPaymentInstructionPrepares,
} from './paymentInstructionPrepareStore.js'

const STORAGE_KEY = 'payment-execution-prepare-state-v1'
const ACTIVE_STATUSES = ['draft', 'waiting_execution_review', 'reviewed', 'blocked']

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

function toNumber(value) {
  const next = Number(value)
  return Number.isFinite(next) ? next : 0
}

function roundAmount(value) {
  return Number(toNumber(value).toFixed(2))
}

function defaultState() {
  return { paymentExecutionPrepares: [] }
}

function byId(collection, id) {
  return (collection || []).find((item) => String(item.id) === String(id)) || null
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[PAYMENT EXECUTION PREPARE STORE] fallback to empty state', error)
    return defaultState()
  }
}

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function appendLog(current, action, beforeStatus, afterStatus, remark = '', operator = 'page-user') {
  current.logs = [
    ...(current.logs || []),
    {
      action,
      beforeStatus,
      afterStatus,
      operator,
      time: nowText(),
      remark: remark || action,
      sourcePaymentOrderPrepareNo: current.sourcePaymentOrderPrepareNo || '',
      paymentExecutionPrepareNo: current.paymentExecutionPrepareNo || '',
    },
  ]
}

function appendPreExecutionLog(current, action, beforeStatus, afterStatus, remark = '', operator = 'page-user', riskStatus = '', blockReasons = []) {
  current.preExecutionLogs = [
    ...(current.preExecutionLogs || []),
    {
      action,
      beforeStatus,
      afterStatus,
      operator,
      time: nowText(),
      remark: remark || action,
      paymentExecutionPrepareNo: current.paymentExecutionPrepareNo || '',
      riskStatus: riskStatus || current.preExecutionRiskStatus || 'warning',
      blockReasons: Array.isArray(blockReasons) ? blockReasons : [],
    },
  ]
}

function appendPaymentExecutionSimulationLog(current, action, beforeStatus, afterStatus, remark = '', operator = 'page-user', simulationResult = '', warnings = [], blockReasons = []) {
  current.paymentExecutionSimulationLogs = [
    ...(current.paymentExecutionSimulationLogs || []),
    {
      action,
      beforeSimulationStatus: beforeStatus,
      afterSimulationStatus: afterStatus,
      operator,
      time: nowText(),
      remark: remark || action,
      paymentExecutionPrepareNo: current.paymentExecutionPrepareNo || '',
      simulationResult: simulationResult || current.paymentExecutionSimulationResult || '',
      warnings: Array.isArray(warnings) ? warnings : [],
      blockReasons: Array.isArray(blockReasons) ? blockReasons : [],
    },
  ]
}

function appendFormalExecutionEntryLog(current, action, beforeStatus, afterStatus, remark = '', operator = 'page-user', warnings = [], blockReasons = []) {
  current.formalExecutionEntryLogs = [
    ...(current.formalExecutionEntryLogs || []),
    {
      action,
      beforeStatus,
      afterStatus,
      operator,
      time: nowText(),
      remark: remark || action,
      paymentExecutionPrepareNo: current.paymentExecutionPrepareNo || '',
      blockReasons: Array.isArray(blockReasons) ? blockReasons : [],
      warnings: Array.isArray(warnings) ? warnings : [],
    },
  ]
}

function evaluatePreExecutionReadiness(current = {}) {
  const blockReasons = []
  const warnings = []
  if (current.paymentExecutionPrepareStatus !== 'reviewed') blockReasons.push('付款执行准备尚未复核通过。')
  if (current.paymentExecutionStatus !== 'not_executed') blockReasons.push('付款执行状态不是未执行。')
  if (current.bankFlowStatus !== 'not_generated') blockReasons.push('银行流水已生成或状态异常。')
  if (current.paymentVoucherStatus !== 'not_generated') blockReasons.push('付款凭证已生成或状态异常。')
  if (current.formalPaymentVoucherStatus !== 'not_generated') blockReasons.push('正式付款凭证已生成或状态异常。')
  if (current.writeOffStatus !== 'not_written_off') blockReasons.push('付款已核销或核销状态异常。')
  if (current.ledgerStatus !== 'not_written_ledger') blockReasons.push('总账已写入或总账状态异常。')
  if (current.postingStatus !== 'not_posted') blockReasons.push('凭证已过账或过账状态异常。')
  if (roundAmount(current.executionAmount) <= 0) blockReasons.push('执行准备金额为空或为 0。')
  if (!current.paymentMethod) blockReasons.push('付款方式缺失。')
  if (!current.sourcePaymentOrderPrepareNo) blockReasons.push('来源付款指令准备单号缺失。')
  if (!current.sourcePaymentApplicationNo) blockReasons.push('来源付款申请单号缺失。')
  if (!current.payeeBankName || !current.payeeBankAccount) warnings.push('收款银行信息待补充，请在真实付款前人工复核。')
  if (current.isDemoChain) warnings.push('当前记录为开发阶段演示链路数据，不属于正式付款业务数据。')
  return {
    preExecutionReady: blockReasons.length === 0,
    preExecutionBlocked: blockReasons.length > 0,
    preExecutionBlockReasons: blockReasons,
    preExecutionWarnings: warnings,
    preExecutionRiskStatus: blockReasons.length ? 'blocked' : warnings.length ? 'warning' : 'normal',
    preExecutionCheckStatus: blockReasons.length ? 'blocked' : 'checked',
  }
}

function evaluatePaymentExecutionSimulation(current = {}) {
  const blockReasons = []
  const warnings = []
  if (!current.preExecutionReady) blockReasons.push('付款执行前安全检查未通过。')
  if (current.preExecutionBlocked) blockReasons.push('付款执行前安全检查已阻断。')
  if (current.paymentExecutionPrepareStatus !== 'reviewed') blockReasons.push('付款执行准备尚未复核通过。')
  if (current.paymentExecutionStatus !== 'not_executed') blockReasons.push('真实付款执行状态不是未执行。')
  if (current.bankFlowStatus !== 'not_generated') blockReasons.push('银行流水已生成或状态异常。')
  if (current.paymentVoucherStatus !== 'not_generated') blockReasons.push('付款凭证已生成或状态异常。')
  if (current.formalPaymentVoucherStatus !== 'not_generated') blockReasons.push('正式付款凭证已生成或状态异常。')
  if (current.writeOffStatus !== 'not_written_off') blockReasons.push('付款已核销或核销状态异常。')
  if (current.ledgerStatus !== 'not_written_ledger') blockReasons.push('总账已写入或总账状态异常。')
  if (current.postingStatus !== 'not_posted') blockReasons.push('凭证已过账或过账状态异常。')
  if (roundAmount(current.executionAmount) <= 0) blockReasons.push('执行准备金额为空或为 0。')
  if (Array.isArray(current.preExecutionWarnings) && current.preExecutionWarnings.length) warnings.push(...current.preExecutionWarnings)
  if (current.isDemoChain) warnings.push('当前记录为开发阶段演示链路数据，模拟结果仅用于本地验证。')
  const uniqueWarnings = [...new Set(warnings.filter(Boolean))]
  const uniqueBlocks = [...new Set(blockReasons.filter(Boolean))]
  const status = uniqueBlocks.length ? 'simulated_blocked' : uniqueWarnings.length ? 'simulated_warning' : 'simulated_ready'
  return {
    paymentExecutionSimulationStatus: status,
    paymentExecutionSimulated: uniqueBlocks.length === 0,
    paymentExecutionSimulationResult: uniqueBlocks.length
      ? '模拟阻断：不满足付款执行模拟前置条件，本轮未付款。'
      : status === 'simulated_warning'
        ? '模拟警告：可模拟进入后续真实付款执行设计，但存在提醒项；本轮未付款。'
        : '模拟通过：可进入后续真实付款执行设计，但本轮未付款。',
    paymentExecutionSimulationWarnings: uniqueWarnings,
    paymentExecutionSimulationBlockReasons: uniqueBlocks,
  }
}

function evaluateFormalExecutionEntry(current = {}) {
  const blockReasons = []
  const warnings = []
  if (current.paymentExecutionPrepareStatus !== 'reviewed') blockReasons.push('付款执行准备尚未复核通过。')
  if (!current.preExecutionReady) blockReasons.push('未完成付款执行前安全检查。')
  if (current.preExecutionBlocked) blockReasons.push('付款执行前安全检查已阻断。')
  if (!['simulated_ready', 'simulated_warning'].includes(current.paymentExecutionSimulationStatus)) blockReasons.push('未完成付款执行模拟或模拟结果不允许进入正式入口。')
  if (current.paymentExecutionSimulationStatus === 'simulated_blocked') blockReasons.push('付款执行模拟结果为阻断。')
  if (current.paymentExecutionStatus !== 'not_executed') blockReasons.push('已执行付款或付款执行状态异常。')
  if (current.bankFlowStatus !== 'not_generated') blockReasons.push('已生成银行流水或银行流水状态异常。')
  if (current.paymentVoucherStatus !== 'not_generated') blockReasons.push('已生成付款凭证或付款凭证状态异常。')
  if (current.formalPaymentVoucherStatus !== 'not_generated') blockReasons.push('已生成正式付款凭证或正式付款凭证状态异常。')
  if (current.writeOffStatus !== 'not_written_off') blockReasons.push('已核销或核销状态异常。')
  if (current.ledgerStatus !== 'not_written_ledger') blockReasons.push('已写总账或总账状态异常。')
  if (current.postingStatus !== 'not_posted') blockReasons.push('已过账或过账状态异常。')
  if (roundAmount(current.executionAmount) <= 0) blockReasons.push('执行准备金额为空或为 0。')
  if (current.paymentExecutionSimulationStatus === 'simulated_warning') warnings.push('付款执行模拟存在警告，正式付款入口仅允许预览，不允许执行。')
  if (current.isDemoChain) warnings.push('当前记录为开发阶段演示链路数据，不属于正式付款业务数据。')
  const uniqueWarnings = [...new Set(warnings.filter(Boolean))]
  const uniqueBlocks = [...new Set(blockReasons.filter(Boolean))]
  return {
    formalExecutionEntryStatus: uniqueBlocks.length ? 'blocked' : 'preview_ready',
    formalExecutionEntryReady: uniqueBlocks.length === 0,
    formalExecutionEntryBlocked: uniqueBlocks.length > 0,
    formalExecutionEntryBlockReasons: uniqueBlocks,
    formalExecutionEntryWarnings: uniqueWarnings,
    actualPaymentExecutionEnabled: false,
  }
}

export function getFormalExecutionEntryDecision(paymentExecutionPrepare = {}) {
  return clone(evaluateFormalExecutionEntry(paymentExecutionPrepare))
}

function paymentExecutionPrepare(payload = {}) {
  const stamp = nowText()
  const orderAmount = roundAmount(payload.orderAmount)
  const executionAmount = roundAmount(payload.executionAmount ?? orderAmount)
  return {
    id: payload.id || createId('payment-execution-prepare'),
    paymentExecutionPrepareNo: payload.paymentExecutionPrepareNo || createNo('PEP'),
    sourcePaymentOrderPrepareId: payload.sourcePaymentOrderPrepareId || '',
    sourcePaymentOrderPrepareNo: payload.sourcePaymentOrderPrepareNo || '',
    sourcePaymentApplicationNo: payload.sourcePaymentApplicationNo || '',
    sourcePayableConfirmNo: payload.sourcePayableConfirmNo || '',
    sourceInvoicePrepareNo: payload.sourceInvoicePrepareNo || '',
    sourceSettlementNo: payload.sourceSettlementNo || '',
    supplierId: payload.supplierId || '',
    supplierName: payload.supplierName || '',
    purchaseOrderNo: payload.purchaseOrderNo || '',
    invoiceNo: payload.invoiceNo || '',
    orderAmount,
    executionAmount,
    currency: payload.currency || 'CNY',
    paymentMethod: payload.paymentMethod || 'bank_transfer',
    plannedPaymentDate: payload.plannedPaymentDate || '',
    paymentPriority: payload.paymentPriority || 'normal',
    paymentPurpose: payload.paymentPurpose || '付款指令签发后的付款执行准备',
    payeeName: payload.payeeName || payload.supplierName || '',
    payeeBankName: payload.payeeBankName || '',
    payeeBankAccount: payload.payeeBankAccount || '',
    payerAccountName: payload.payerAccountName || '',
    payerBankName: payload.payerBankName || '',
    payerBankAccount: payload.payerBankAccount || '',
    paymentExecutionPrepareStatus: payload.paymentExecutionPrepareStatus || 'draft',
    paymentExecutionStatus: payload.paymentExecutionStatus || 'not_executed',
    bankFlowStatus: payload.bankFlowStatus || 'not_generated',
    paymentVoucherStatus: payload.paymentVoucherStatus || 'not_generated',
    formalPaymentVoucherStatus: payload.formalPaymentVoucherStatus || 'not_generated',
    writeOffStatus: payload.writeOffStatus || 'not_written_off',
    ledgerStatus: payload.ledgerStatus || 'not_written_ledger',
    postingStatus: payload.postingStatus || 'not_posted',
    executionRiskStatus: payload.executionRiskStatus || 'not_checked',
    preExecutionCheckStatus: payload.preExecutionCheckStatus || 'not_checked',
    preExecutionRiskStatus: payload.preExecutionRiskStatus || 'warning',
    preExecutionReady: Boolean(payload.preExecutionReady),
    preExecutionBlocked: Boolean(payload.preExecutionBlocked),
    preExecutionBlockReasons: Array.isArray(payload.preExecutionBlockReasons) ? payload.preExecutionBlockReasons : [],
    preExecutionWarnings: Array.isArray(payload.preExecutionWarnings) ? payload.preExecutionWarnings : [],
    preExecutionCheckedAt: payload.preExecutionCheckedAt || '',
    preExecutionCheckedBy: payload.preExecutionCheckedBy || '',
    preExecutionLogs: Array.isArray(payload.preExecutionLogs) ? payload.preExecutionLogs : [],
    paymentExecutionSimulationStatus: payload.paymentExecutionSimulationStatus || 'not_simulated',
    paymentExecutionSimulated: Boolean(payload.paymentExecutionSimulated),
    paymentExecutionSimulatedAt: payload.paymentExecutionSimulatedAt || '',
    paymentExecutionSimulatedBy: payload.paymentExecutionSimulatedBy || '',
    paymentExecutionSimulationResult: payload.paymentExecutionSimulationResult || '',
    paymentExecutionSimulationWarnings: Array.isArray(payload.paymentExecutionSimulationWarnings) ? payload.paymentExecutionSimulationWarnings : [],
    paymentExecutionSimulationBlockReasons: Array.isArray(payload.paymentExecutionSimulationBlockReasons) ? payload.paymentExecutionSimulationBlockReasons : [],
    paymentExecutionSimulationLogs: Array.isArray(payload.paymentExecutionSimulationLogs) ? payload.paymentExecutionSimulationLogs : [],
    formalExecutionEntryStatus: payload.formalExecutionEntryStatus || 'not_ready',
    formalExecutionEntryReady: Boolean(payload.formalExecutionEntryReady),
    formalExecutionEntryBlocked: Boolean(payload.formalExecutionEntryBlocked),
    formalExecutionEntryBlockReasons: Array.isArray(payload.formalExecutionEntryBlockReasons) ? payload.formalExecutionEntryBlockReasons : [],
    formalExecutionEntryWarnings: Array.isArray(payload.formalExecutionEntryWarnings) ? payload.formalExecutionEntryWarnings : [],
    formalExecutionEntryReviewedAt: payload.formalExecutionEntryReviewedAt || '',
    formalExecutionEntryReviewedBy: payload.formalExecutionEntryReviewedBy || '',
    formalExecutionEntryPreviewCount: Number(payload.formalExecutionEntryPreviewCount || 0),
    formalExecutionEntryLogs: Array.isArray(payload.formalExecutionEntryLogs) ? payload.formalExecutionEntryLogs : [],
    actualPaymentExecutionEnabled: false,
    isDemoChain: Boolean(payload.isDemoChain),
    demoChainVersion: payload.demoChainVersion || '',
    demoChainGeneratedAt: payload.demoChainGeneratedAt || '',
    demoChainPurpose: payload.demoChainPurpose || '',
    remark: payload.remark || '',
    createdAt: payload.createdAt || stamp,
    createdBy: payload.createdBy || 'system',
    updatedAt: payload.updatedAt || stamp,
    logs: Array.isArray(payload.logs) ? payload.logs : [],
  }
}

function normalizeState(raw = {}) {
  return { paymentExecutionPrepares: (raw.paymentExecutionPrepares || []).map(paymentExecutionPrepare) }
}

let state = loadState()

export function writePaymentExecutionPrepareLog(action, payload = {}) {
  addOperationLog({
    module: '付款执行准备',
    action,
    targetType: payload.targetType || 'paymentExecutionPrepare',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: [
      `来源付款指令准备：${payload.sourceNo || '-'}`,
      `目标付款执行准备：${payload.targetNo || '-'}`,
      `结果：${payload.result || '成功'}`,
    ].join('；'),
  })
}

export function getPaymentExecutionPrepareState() {
  return clone(state)
}

export function savePaymentExecutionPrepareState(nextState) {
  state = normalizeState(nextState)
  persist()
  writePaymentExecutionPrepareLog('save_payment_execution_prepare_state', { targetType: 'paymentExecutionPrepareState', targetId: 'state' })
  return getPaymentExecutionPrepareState()
}

export function listPaymentExecutionPrepares() {
  return clone(state.paymentExecutionPrepares)
}

export function getPaymentExecutionPrepareById(id) {
  return clone(byId(state.paymentExecutionPrepares, id))
}

export function isPaymentExecutionPrepareGeneratedFromPaymentOrderPrepare(paymentOrderPrepareOrId) {
  const paymentOrderPrepare = typeof paymentOrderPrepareOrId === 'object'
    ? paymentOrderPrepareOrId
    : getPaymentInstructionPrepareById(paymentOrderPrepareOrId)
  if (!paymentOrderPrepare?.id) return false
  if (paymentOrderPrepare.linkedPaymentExecutionPrepareId || paymentOrderPrepare.linkedPaymentExecutionPrepareNo) return true
  return state.paymentExecutionPrepares.some((item) => (
    String(item.sourcePaymentOrderPrepareId) === String(paymentOrderPrepare.id)
    && ACTIVE_STATUSES.includes(item.paymentExecutionPrepareStatus)
  ))
}

export function getPaymentExecutionPrepareCreateGuard(paymentOrderPrepare = {}) {
  if (!paymentOrderPrepare?.id) return { canCreate: false, reason: '未找到付款指令准备。' }
  if (isPaymentExecutionPrepareGeneratedFromPaymentOrderPrepare(paymentOrderPrepare)) return { canCreate: false, reason: '已存在付款执行准备，不能重复生成。' }
  if (paymentOrderPrepare.paymentOrderStatus !== 'reviewed') return { canCreate: false, reason: '付款指令准备尚未复核通过。' }
  if (paymentOrderPrepare.paymentInstructionStatus !== 'ready_to_issue') return { canCreate: false, reason: '付款指令状态不是可签发。' }
  if (roundAmount(paymentOrderPrepare.orderAmount) <= 0) return { canCreate: false, reason: '付款指令金额为空或为 0。' }
  if (!['not_started', 'not_executed'].includes(paymentOrderPrepare.paymentExecutionStatus || 'not_started')) return { canCreate: false, reason: '付款执行状态不是未开始。' }
  if (paymentOrderPrepare.paymentVoucherStatus !== 'not_generated') return { canCreate: false, reason: '付款凭证状态不是未生成。' }
  if (paymentOrderPrepare.writeOffStatus !== 'not_written_off') return { canCreate: false, reason: '核销状态不是未核销。' }
  if (paymentOrderPrepare.ledgerStatus !== 'not_written_ledger') return { canCreate: false, reason: '总账状态不是未写总账。' }
  if (paymentOrderPrepare.postingStatus !== 'not_posted') return { canCreate: false, reason: '过账状态不是未过账。' }
  if (['blocked', 'closed'].includes(paymentOrderPrepare.paymentOrderStatus)) return { canCreate: false, reason: '付款指令准备已阻断或关闭。' }
  return { canCreate: true, reason: '' }
}

export function getPaymentExecutionPrepareSourcesFromPaymentOrderPrepares() {
  return listPaymentInstructionPrepares().map((paymentOrderPrepare) => {
    const existed = state.paymentExecutionPrepares.find((item) => (
      String(item.sourcePaymentOrderPrepareId) === String(paymentOrderPrepare.id)
      && ACTIVE_STATUSES.includes(item.paymentExecutionPrepareStatus)
    ))
    const generated = isPaymentExecutionPrepareGeneratedFromPaymentOrderPrepare(paymentOrderPrepare)
    const guard = getPaymentExecutionPrepareCreateGuard(paymentOrderPrepare)
    return {
      ...paymentOrderPrepare,
      paymentExecutionPrepareGenerated: generated,
      paymentExecutionPrepareGeneratedText: generated ? '已生成付款执行准备' : '未生成',
      linkedPaymentExecutionPrepareId: paymentOrderPrepare.linkedPaymentExecutionPrepareId || existed?.id || '',
      linkedPaymentExecutionPrepareNo: paymentOrderPrepare.linkedPaymentExecutionPrepareNo || existed?.paymentExecutionPrepareNo || '',
      canCreatePaymentExecutionPrepare: guard.canCreate,
      paymentExecutionPrepareBlockReason: guard.reason,
    }
  })
}

export function createPaymentExecutionPrepareFromPaymentOrderPrepare(paymentOrderPrepareId, operator = 'page-user') {
  const paymentOrderPrepare = getPaymentInstructionPrepareById(paymentOrderPrepareId)
  const guard = getPaymentExecutionPrepareCreateGuard(paymentOrderPrepare)
  if (!guard.canCreate) {
    writePaymentExecutionPrepareLog('create_from_payment_order_prepare_blocked', {
      sourceNo: paymentOrderPrepare?.paymentOrderPrepareNo || paymentOrderPrepareId,
      targetId: paymentOrderPrepareId,
      result: guard.reason,
    })
    return { success: false, error: guard.reason, paymentOrderPrepare }
  }

  const amount = roundAmount(paymentOrderPrepare.orderAmount)
  const prepare = paymentExecutionPrepare({
    sourcePaymentOrderPrepareId: paymentOrderPrepare.id,
    sourcePaymentOrderPrepareNo: paymentOrderPrepare.paymentOrderPrepareNo,
    sourcePaymentApplicationNo: paymentOrderPrepare.sourcePaymentApplicationNo,
    sourcePayableConfirmNo: paymentOrderPrepare.sourcePayableConfirmNo,
    sourceInvoicePrepareNo: paymentOrderPrepare.sourceInvoicePrepareNo,
    sourceSettlementNo: paymentOrderPrepare.sourceSettlementNo,
    supplierId: paymentOrderPrepare.supplierId,
    supplierName: paymentOrderPrepare.supplierName,
    purchaseOrderNo: paymentOrderPrepare.purchaseOrderNo,
    invoiceNo: paymentOrderPrepare.invoiceNo,
    orderAmount: amount,
    executionAmount: amount,
    currency: paymentOrderPrepare.currency || 'CNY',
    paymentMethod: paymentOrderPrepare.paymentMethod || 'bank_transfer',
    plannedPaymentDate: paymentOrderPrepare.plannedPaymentDate || '',
    paymentPriority: paymentOrderPrepare.paymentPriority || 'normal',
    paymentPurpose: paymentOrderPrepare.paymentPurpose || '付款指令签发后的付款执行准备',
    payeeName: paymentOrderPrepare.payeeName || paymentOrderPrepare.supplierName,
    payeeBankName: paymentOrderPrepare.payeeBankName || '',
    payeeBankAccount: paymentOrderPrepare.payeeBankAccount || '',
    payerAccountName: paymentOrderPrepare.payerAccountName || '',
    payerBankName: paymentOrderPrepare.payerBankName || '',
    payerBankAccount: paymentOrderPrepare.payerBankAccount || '',
    remark: '由已复核且可签发的付款指令准备生成付款执行准备；不真实付款、不生成银行流水、不生成凭证、不核销、不写总账。',
    createdBy: operator,
  })
  appendLog(prepare, 'create_from_payment_order_prepare', '', prepare.paymentExecutionPrepareStatus, '由付款指令准备签发生成付款执行准备。', operator)
  state.paymentExecutionPrepares.unshift(prepare)
  persist()
  const writeBack = linkPaymentOrderPrepareExecutionPrepare(paymentOrderPrepare.id, prepare, operator)
  writePaymentExecutionPrepareLog('create_from_payment_order_prepare', {
    sourceNo: paymentOrderPrepare.paymentOrderPrepareNo,
    targetId: prepare.id,
    targetNo: prepare.paymentExecutionPrepareNo,
    result: amount,
  })
  return {
    success: true,
    paymentExecutionPrepareId: prepare.id,
    paymentExecutionPrepareNo: prepare.paymentExecutionPrepareNo,
    paymentExecutionPrepare: clone(prepare),
    writeBackSuccess: Boolean(writeBack?.success),
  }
}

export function recalculatePaymentExecutionPrepareAmount(id, operator = 'page-user') {
  const current = byId(state.paymentExecutionPrepares, id)
  if (!current) return { success: false, error: '未找到付款执行准备。' }
  const beforeStatus = current.paymentExecutionPrepareStatus
  current.executionAmount = roundAmount(current.orderAmount)
  current.executionRiskStatus = current.executionAmount > 0 ? 'not_checked' : 'blocked'
  if (current.executionAmount <= 0) current.paymentExecutionPrepareStatus = 'blocked'
  current.updatedAt = nowText()
  appendLog(current, 'recalculate_payment_execution_amount', beforeStatus, current.paymentExecutionPrepareStatus, '重算执行准备金额；不真实付款。', operator)
  persist()
  writePaymentExecutionPrepareLog('recalculate_payment_execution_amount', { targetId: current.id, targetNo: current.paymentExecutionPrepareNo, result: current.executionAmount })
  return { success: true, paymentExecutionPrepare: clone(current) }
}

export function updatePaymentExecutionPrepareInfo(id, patch = {}, operator = 'page-user') {
  const current = byId(state.paymentExecutionPrepares, id)
  if (!current) return { success: false, error: '未找到付款执行准备。' }
  if (['closed', 'reviewed'].includes(current.paymentExecutionPrepareStatus)) return { success: false, error: '已复核或已关闭的付款执行准备不能继续编辑。' }
  const beforeStatus = current.paymentExecutionPrepareStatus
  Object.assign(current, {
    executionAmount: roundAmount(patch.executionAmount ?? current.executionAmount),
    paymentMethod: patch.paymentMethod ?? current.paymentMethod,
    plannedPaymentDate: patch.plannedPaymentDate ?? current.plannedPaymentDate,
    paymentPriority: patch.paymentPriority ?? current.paymentPriority,
    paymentPurpose: patch.paymentPurpose ?? current.paymentPurpose,
    payeeName: patch.payeeName ?? current.payeeName,
    payeeBankName: patch.payeeBankName ?? current.payeeBankName,
    payeeBankAccount: patch.payeeBankAccount ?? current.payeeBankAccount,
    payerAccountName: patch.payerAccountName ?? current.payerAccountName,
    payerBankName: patch.payerBankName ?? current.payerBankName,
    payerBankAccount: patch.payerBankAccount ?? current.payerBankAccount,
    remark: patch.remark ?? current.remark,
    updatedAt: nowText(),
  })
  if (current.executionAmount > current.orderAmount) {
    current.paymentExecutionPrepareStatus = 'blocked'
    current.executionRiskStatus = 'blocked'
    current.remark = current.remark || '执行准备金额超过付款指令金额，已阻断复核。'
  }
  appendLog(current, 'edit_payment_execution_prepare', beforeStatus, current.paymentExecutionPrepareStatus, '编辑付款执行准备信息；不真实付款。', operator)
  persist()
  writePaymentExecutionPrepareLog('edit_payment_execution_prepare', { targetId: current.id, targetNo: current.paymentExecutionPrepareNo })
  return { success: true, paymentExecutionPrepare: clone(current) }
}

function markStatus(id, nextStatus, action, patch = {}, remark = '', operator = 'page-user') {
  const current = byId(state.paymentExecutionPrepares, id)
  if (!current) return { success: false, error: '未找到付款执行准备。' }
  if (current.paymentExecutionPrepareStatus === 'closed' && nextStatus !== 'closed') return { success: false, error: '已关闭的付款执行准备不能继续流转。' }
  const beforeStatus = current.paymentExecutionPrepareStatus
  Object.assign(current, patch, {
    paymentExecutionPrepareStatus: nextStatus,
    updatedAt: nowText(),
  })
  appendLog(current, action, beforeStatus, nextStatus, remark, operator)
  persist()
  writePaymentExecutionPrepareLog(action, { targetId: current.id, targetNo: current.paymentExecutionPrepareNo, result: nextStatus })
  return { success: true, paymentExecutionPrepare: clone(current) }
}

export function markPaymentExecutionPrepareWaitingReview(id, operator = 'page-user') {
  const current = byId(state.paymentExecutionPrepares, id)
  if (!current) return { success: false, error: '未找到付款执行准备。' }
  if (current.executionAmount <= 0) return { success: false, error: '执行准备金额为空或为 0。' }
  if (current.executionAmount > current.orderAmount) return { success: false, error: '执行准备金额超过付款指令金额，不能进入待复核。' }
  return markStatus(id, 'waiting_execution_review', 'mark_waiting_execution_review', { paymentExecutionStatus: 'not_executed' }, '标记为待执行复核；不真实付款。', operator)
}

export function reviewPaymentExecutionPrepare(id, operator = 'page-user') {
  const current = byId(state.paymentExecutionPrepares, id)
  if (!current) return { success: false, error: '未找到付款执行准备。' }
  if (!['draft', 'waiting_execution_review'].includes(current.paymentExecutionPrepareStatus)) return { success: false, error: '只有草稿或待执行复核状态可以复核通过。' }
  if (current.executionAmount <= 0) return { success: false, error: '执行准备金额为空或为 0。' }
  if (current.executionAmount > current.orderAmount) return { success: false, error: '执行准备金额超过付款指令金额，不能复核通过。' }
  return markStatus(id, 'reviewed', 'review_payment_execution_prepare', {
    paymentExecutionStatus: 'not_executed',
    bankFlowStatus: 'not_generated',
    paymentVoucherStatus: 'not_generated',
    formalPaymentVoucherStatus: 'not_generated',
    writeOffStatus: 'not_written_off',
    ledgerStatus: 'not_written_ledger',
    postingStatus: 'not_posted',
    executionRiskStatus: 'not_checked',
  }, '付款执行准备复核通过；不真实付款、不生成银行流水、不生成凭证、不核销、不写总账。', operator)
}

export function blockPaymentExecutionPrepare(id, remark = '付款执行准备异常阻断，待人工处理。', operator = 'page-user') {
  return markStatus(id, 'blocked', 'block_payment_execution_prepare', { executionRiskStatus: 'blocked', remark }, remark, operator)
}

export function closePaymentExecutionPrepare(id, remark = '关闭付款执行准备。', operator = 'page-user') {
  return markStatus(id, 'closed', 'close_payment_execution_prepare', { remark }, remark, operator)
}

export function runPaymentExecutionPreExecutionCheck(id, operator = 'page-user') {
  const current = byId(state.paymentExecutionPrepares, id)
  if (!current) return { success: false, error: '未找到付款执行准备。' }
  const beforeStatus = current.preExecutionCheckStatus || 'not_checked'
  const decision = evaluatePreExecutionReadiness(current)
  Object.assign(current, decision, {
    preExecutionCheckedAt: nowText(),
    preExecutionCheckedBy: operator,
    updatedAt: nowText(),
  })
  appendPreExecutionLog(
    current,
    'run_pre_execution_check',
    beforeStatus,
    current.preExecutionCheckStatus,
    decision.preExecutionReady ? '付款执行入口预检通过；本轮仍不执行付款。' : '付款执行入口预检被阻断；本轮不执行付款。',
    operator,
    current.preExecutionRiskStatus,
    current.preExecutionBlockReasons,
  )
  persist()
  writePaymentExecutionPrepareLog('run_pre_execution_check', {
    targetId: current.id,
    targetNo: current.paymentExecutionPrepareNo,
    result: current.preExecutionCheckStatus,
  })
  return { success: true, paymentExecutionPrepare: clone(current), decision: clone(decision) }
}

export function openPaymentExecutionEntryPreview(id, operator = 'page-user') {
  const current = byId(state.paymentExecutionPrepares, id)
  if (!current) return { success: false, error: '未找到付款执行准备。' }
  const beforeStatus = current.preExecutionCheckStatus || 'not_checked'
  const decision = evaluatePreExecutionReadiness(current)
  Object.assign(current, decision, {
    preExecutionCheckedAt: current.preExecutionCheckedAt || nowText(),
    preExecutionCheckedBy: current.preExecutionCheckedBy || operator,
    updatedAt: nowText(),
  })
  appendPreExecutionLog(
    current,
    'open_payment_execution_entry_preview',
    beforeStatus,
    current.preExecutionCheckStatus,
    decision.preExecutionReady ? '打开付款执行入口预览；本轮不执行付款。' : '付款执行入口预览被阻断。',
    operator,
    current.preExecutionRiskStatus,
    current.preExecutionBlockReasons,
  )
  persist()
  if (!decision.preExecutionReady) {
    return {
      success: false,
      error: decision.preExecutionBlockReasons.join('；') || '付款执行入口被阻断。',
      paymentExecutionPrepare: clone(current),
      decision: clone(decision),
    }
  }
  return { success: true, paymentExecutionPrepare: clone(current), decision: clone(decision) }
}

export function confirmPaymentExecutionEntryPreviewNoExecution(id, operator = 'page-user') {
  const current = byId(state.paymentExecutionPrepares, id)
  if (!current) return { success: false, error: '未找到付款执行准备。' }
  appendPreExecutionLog(
    current,
    'confirm_entry_preview_no_execution',
    current.preExecutionCheckStatus || 'not_checked',
    current.preExecutionCheckStatus || 'not_checked',
    '用户已确认本轮仅预览付款执行入口，不执行付款、不生成银行流水、不生成凭证、不核销、不写总账。',
    operator,
    current.preExecutionRiskStatus,
    current.preExecutionBlockReasons,
  )
  current.updatedAt = nowText()
  persist()
  return { success: true, paymentExecutionPrepare: clone(current) }
}

export function runPaymentExecutionSimulation(id, operator = 'page-user') {
  const current = byId(state.paymentExecutionPrepares, id)
  if (!current) return { success: false, error: '未找到付款执行准备。' }
  const beforeStatus = current.paymentExecutionSimulationStatus || 'not_simulated'
  const decision = evaluatePaymentExecutionSimulation(current)
  Object.assign(current, decision, {
    paymentExecutionSimulatedAt: nowText(),
    paymentExecutionSimulatedBy: operator,
    updatedAt: nowText(),
  })
  appendPaymentExecutionSimulationLog(
    current,
    'run_payment_execution_simulation',
    beforeStatus,
    current.paymentExecutionSimulationStatus,
    '运行付款执行模拟状态机；本轮不真实付款。',
    operator,
    current.paymentExecutionSimulationResult,
    current.paymentExecutionSimulationWarnings,
    current.paymentExecutionSimulationBlockReasons,
  )
  appendPaymentExecutionSimulationLog(
    current,
    current.paymentExecutionSimulationStatus === 'simulated_blocked'
      ? 'simulation_blocked'
      : current.paymentExecutionSimulationStatus === 'simulated_warning'
        ? 'simulation_warning'
        : 'simulation_ready',
    beforeStatus,
    current.paymentExecutionSimulationStatus,
    current.paymentExecutionSimulationResult,
    operator,
    current.paymentExecutionSimulationResult,
    current.paymentExecutionSimulationWarnings,
    current.paymentExecutionSimulationBlockReasons,
  )
  persist()
  writePaymentExecutionPrepareLog('run_payment_execution_simulation', {
    targetId: current.id,
    targetNo: current.paymentExecutionPrepareNo,
    result: current.paymentExecutionSimulationStatus,
  })
  return { success: true, paymentExecutionPrepare: clone(current), decision: clone(decision) }
}

export function runFormalExecutionEntryCheck(id, operator = 'page-user') {
  const current = byId(state.paymentExecutionPrepares, id)
  if (!current) return { success: false, error: '未找到付款执行准备。' }
  const beforeStatus = current.formalExecutionEntryStatus || 'not_ready'
  const decision = evaluateFormalExecutionEntry(current)
  Object.assign(current, decision, {
    formalExecutionEntryReviewedAt: nowText(),
    formalExecutionEntryReviewedBy: operator,
    updatedAt: nowText(),
  })
  appendFormalExecutionEntryLog(
    current,
    'run_formal_execution_entry_check',
    beforeStatus,
    current.formalExecutionEntryStatus,
    decision.formalExecutionEntryReady ? '正式付款执行入口预览条件已通过；真实付款功能仍强制关闭。' : '正式付款执行入口预览被阻断；真实付款功能仍强制关闭。',
    operator,
    current.formalExecutionEntryWarnings,
    current.formalExecutionEntryBlockReasons,
  )
  persist()
  writePaymentExecutionPrepareLog('run_formal_execution_entry_check', {
    targetId: current.id,
    targetNo: current.paymentExecutionPrepareNo,
    result: current.formalExecutionEntryStatus,
  })
  return { success: true, paymentExecutionPrepare: clone(current), decision: clone(decision) }
}

export function openFormalExecutionEntryPreview(id, operator = 'page-user') {
  const current = byId(state.paymentExecutionPrepares, id)
  if (!current) return { success: false, error: '未找到付款执行准备。' }
  const beforeStatus = current.formalExecutionEntryStatus || 'not_ready'
  const decision = evaluateFormalExecutionEntry(current)
  Object.assign(current, decision, {
    formalExecutionEntryReviewedAt: current.formalExecutionEntryReviewedAt || nowText(),
    formalExecutionEntryReviewedBy: current.formalExecutionEntryReviewedBy || operator,
    updatedAt: nowText(),
  })
  appendFormalExecutionEntryLog(
    current,
    'open_formal_execution_entry_preview',
    beforeStatus,
    current.formalExecutionEntryStatus,
    decision.formalExecutionEntryReady ? '打开正式付款执行入口预览；本轮仍不执行付款。' : '正式付款执行入口预览被阻断。',
    operator,
    current.formalExecutionEntryWarnings,
    current.formalExecutionEntryBlockReasons,
  )
  persist()
  if (!decision.formalExecutionEntryReady) {
    return {
      success: false,
      error: decision.formalExecutionEntryBlockReasons.join('；') || '正式付款执行入口预览被阻断。',
      paymentExecutionPrepare: clone(current),
      decision: clone(decision),
    }
  }
  return { success: true, paymentExecutionPrepare: clone(current), decision: clone(decision) }
}

export function confirmFormalExecutionEntryPreviewNoExecution(id, operator = 'page-user') {
  const current = byId(state.paymentExecutionPrepares, id)
  if (!current) return { success: false, error: '未找到付款执行准备。' }
  const beforeStatus = current.formalExecutionEntryStatus || 'not_ready'
  current.formalExecutionEntryStatus = current.formalExecutionEntryReady ? 'reviewed_only' : current.formalExecutionEntryStatus
  current.formalExecutionEntryPreviewCount = Number(current.formalExecutionEntryPreviewCount || 0) + 1
  current.actualPaymentExecutionEnabled = false
  current.updatedAt = nowText()
  appendFormalExecutionEntryLog(
    current,
    'confirm_formal_entry_preview_no_execution',
    beforeStatus,
    current.formalExecutionEntryStatus,
    '用户已确认本轮仅预览正式付款执行入口，不执行付款、不生成银行流水、不生成凭证、不核销、不写总账。',
    operator,
    current.formalExecutionEntryWarnings,
    current.formalExecutionEntryBlockReasons,
  )
  persist()
  return { success: true, paymentExecutionPrepare: clone(current) }
}

export function blockActualPaymentExecution(id, operator = 'page-user') {
  const current = byId(state.paymentExecutionPrepares, id)
  if (!current) return { success: false, error: '未找到付款执行准备。' }
  current.actualPaymentExecutionEnabled = false
  appendFormalExecutionEntryLog(
    current,
    'blocked_actual_payment_execution',
    current.formalExecutionEntryStatus || 'not_ready',
    current.formalExecutionEntryStatus || 'not_ready',
    '当前版本未开启真实付款执行，误触发真实付款执行已被强制阻断。',
    operator,
    current.formalExecutionEntryWarnings,
    ['当前版本未开启真实付款执行。'],
  )
  current.updatedAt = nowText()
  persist()
  return { success: false, error: '当前版本未开启真实付款执行。', paymentExecutionPrepare: clone(current) }
}
