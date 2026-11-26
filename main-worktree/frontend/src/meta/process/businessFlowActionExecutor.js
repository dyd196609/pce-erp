import {
  findPurchasePayablePaymentAction,
  findPurchasePayablePaymentActionByStepId,
  terminalPaymentApplicationNotice,
} from './purchasePayablePaymentActionRegistry.js'
import {
  buildSourceWritebackPatch,
  buildTargetSourcePatch,
  evaluateNextStepRelease,
  getRecordAmount,
  getRecordNo,
  isPositiveAmount,
} from './businessFlowStatusAdapter.js'
import { runBusinessFlowTransaction } from './businessFlowTransactionCoordinator.js'
import {
  addBusinessFlowLink,
  findBusinessFlowLinkBySource,
  getBusinessFlowLinkState,
  saveBusinessFlowLinkState,
} from './businessFlowLinkStore.js'
import {
  addBusinessFlowActionAudit,
  getBusinessFlowActionAuditState,
  saveBusinessFlowActionAuditState,
} from './businessFlowActionAuditStore.js'

import { getWmsState, saveWmsState } from '../wms/wmsStore.js'
import {
  createPayablePrepareFromInventoryTransaction,
  getPayablePrepareSourcesFromInventory,
  getPayablePrepareState,
  listPayablePrepares,
  savePayablePrepareState,
} from '../finance/payablePrepareStore.js'
import {
  createPayableCheckFromPayablePrepare,
  getPayableCheckSourcesFromPayablePrepares,
  getPayableCheckState,
  listPayableChecks,
  markPayableCheckChecked,
  savePayableCheckState,
} from '../finance/payableCheckStore.js'
import {
  createSupplierSettlementDraft,
  getSupplierSettlementState,
  listSupplierSettlements,
  saveSupplierSettlementState,
} from '../scm/supplierSettlementStore.js'
import {
  getInvoicePrepareState,
  listInvoicePrepares,
  saveInvoicePrepareState,
} from '../finance/invoicePrepareStore.js'
import {
  createApDraftFromInvoicePrepare,
  getAccountPayableDraftState,
  getApDraftSourcesFromInvoicePrepares,
  listAccountPayableDrafts,
  saveAccountPayableDraftState,
} from '../finance/accountPayableDraftStore.js'
import {
  confirmAccountPayable,
  getAccountPayableConfirmState,
  listAccountPayableConfirms,
  saveAccountPayableConfirmState,
} from '../finance/accountPayableConfirmStore.js'
import {
  createPaymentApplicationFromPayableConfirm,
  getPaymentApplicationSourcesFromPayableConfirms,
  getPaymentApplicationState,
  listPaymentApplications,
  savePaymentApplicationState,
} from '../finance/paymentApplicationStore.js'

export const BUSINESS_FLOW_ACTION_EXECUTOR_VERSION = 'V1.14.2'

function clone(value) {
  return JSON.parse(JSON.stringify(value ?? null))
}

function createId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

function createNo(prefix) {
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)
  return `${prefix}${stamp}${Math.floor(Math.random() * 90 + 10)}`
}

function roundAmount(value) {
  const next = Number(value)
  return Number.isFinite(next) ? Number(next.toFixed(2)) : 0
}

const storeParticipants = [
  { name: 'wms', getState: getWmsState, saveState: saveWmsState },
  { name: 'payablePrepare', getState: getPayablePrepareState, saveState: savePayablePrepareState },
  { name: 'payableCheck', getState: getPayableCheckState, saveState: savePayableCheckState },
  { name: 'supplierSettlement', getState: getSupplierSettlementState, saveState: saveSupplierSettlementState },
  { name: 'invoicePrepare', getState: getInvoicePrepareState, saveState: saveInvoicePrepareState },
  { name: 'accountPayableDraft', getState: getAccountPayableDraftState, saveState: saveAccountPayableDraftState },
  { name: 'accountPayableConfirm', getState: getAccountPayableConfirmState, saveState: saveAccountPayableConfirmState },
  { name: 'paymentApplication', getState: getPaymentApplicationState, saveState: savePaymentApplicationState },
  { name: 'flowLink', getState: getBusinessFlowLinkState, saveState: saveBusinessFlowLinkState },
  { name: 'flowAudit', getState: getBusinessFlowActionAuditState, saveState: saveBusinessFlowActionAuditState },
]

function patchById(state, collectionName, id, patch) {
  const next = clone(state)
  const list = next?.[collectionName] || []
  const index = list.findIndex((item) => String(item.id) === String(id))
  if (index < 0) return { success: false, state }
  list[index] = { ...list[index], ...patch, updatedAt: new Date().toISOString() }
  return { success: true, state: next, record: clone(list[index]) }
}

const sourceStore = {
  inventoryTransaction: {
    getState: getWmsState,
    saveState: saveWmsState,
    collectionName: 'inventoryTransactions',
  },
  payablePrepare: {
    getState: getPayablePrepareState,
    saveState: savePayablePrepareState,
    collectionName: 'payablePrepares',
  },
  payableCheck: {
    getState: getPayableCheckState,
    saveState: savePayableCheckState,
    collectionName: 'payableChecks',
  },
  supplierSettlement: {
    getState: getSupplierSettlementState,
    saveState: saveSupplierSettlementState,
    collectionName: 'supplierSettlements',
  },
  invoicePrepare: {
    getState: getInvoicePrepareState,
    saveState: saveInvoicePrepareState,
    collectionName: 'invoicePrepares',
  },
  accountPayableDraft: {
    getState: getAccountPayableDraftState,
    saveState: saveAccountPayableDraftState,
    collectionName: 'accountPayableDrafts',
  },
  accountPayableConfirm: {
    getState: getAccountPayableConfirmState,
    saveState: saveAccountPayableConfirmState,
    collectionName: 'accountPayableConfirms',
  },
  paymentApplication: {
    getState: getPaymentApplicationState,
    saveState: savePaymentApplicationState,
    collectionName: 'paymentApplications',
  },
}

const targetStore = {
  payablePrepare: { list: listPayablePrepares, ...sourceStore.payablePrepare },
  payableCheck: { list: listPayableChecks, ...sourceStore.payableCheck },
  supplierSettlement: { list: listSupplierSettlements, ...sourceStore.supplierSettlement },
  invoicePrepare: { list: listInvoicePrepares, ...sourceStore.invoicePrepare },
  accountPayableDraft: { list: listAccountPayableDrafts, ...sourceStore.accountPayableDraft },
  accountPayableConfirm: { list: listAccountPayableConfirms, ...sourceStore.accountPayableConfirm },
  paymentApplication: { list: listPaymentApplications, ...sourceStore.paymentApplication },
}

function patchRecord(store, id, patch) {
  const patched = patchById(store.getState(), store.collectionName, id, patch)
  if (!patched.success) return { success: false }
  store.saveState(patched.state)
  return { success: true, record: patched.record }
}

function findTargetBySource(action, source) {
  const link = findBusinessFlowLinkBySource(action.actionCode, action.sourceObjectType, source?.id)
  if (link?.targetObjectNo) {
    const store = targetStore[action.targetObjectType]
    const target = store?.list().find((item) => (
      String(item.id) === String(link.targetObjectId)
      || String(getRecordNo(item, action.targetNoField)) === String(link.targetObjectNo)
    ))
    if (target) return target
  }

  const list = targetStore[action.targetObjectType]?.list() || []
  return list.find((item) => {
    if (item.sourceObjectType === action.sourceObjectType && String(item.sourceObjectId) === String(source?.id)) return true
    if (action.actionCode === 'CREATE_PAYABLE_PREPARE') return (item.sourceInventoryTransactionIds || []).includes(source?.id)
    if (action.actionCode === 'COMPLETE_PAYABLE_CHECK') return String(item.sourcePayablePrepareId) === String(source?.id)
    if (action.actionCode === 'CREATE_PURCHASE_INVOICE_PREPARE') return String(item.sourceSettlementId) === String(source?.id)
    if (action.actionCode === 'CREATE_ACCOUNT_PAYABLE_DRAFT') return String(item.sourceInvoicePrepareId) === String(source?.id)
    if (action.actionCode === 'CREATE_PAYMENT_APPLICATION') return String(item.sourcePayableConfirmId) === String(source?.id)
    return false
  }) || null
}

function firstEligible(items = [], eligibleField, alreadyField) {
  return items.find((item) => item[eligibleField] === true)
    || items.find((item) => item[alreadyField] === true)
    || items[0]
    || null
}

function getPayableCheckSourcesForSettlement() {
  return listPayableChecks().map((check) => {
    const existed = findTargetBySource(findPurchasePayablePaymentAction('CREATE_SUPPLIER_SETTLEMENT'), check)
    const statusReady = ['checked', 'invoicePrepareReady', 'invoicePrepared'].includes(check.checkStatus)
    return {
      ...check,
      canCreateSupplierSettlement: statusReady && !existed,
      supplierSettlementGenerated: Boolean(existed),
      sourceRejectReason: !statusReady ? '应付核对尚未完成。' : (existed ? '已存在供应商结算。' : ''),
    }
  })
}

function getAccountPayableDraftSourcesForConfirm() {
  return listAccountPayableDrafts().map((draft) => {
    const action = findPurchasePayablePaymentAction('CONFIRM_ACCOUNT_PAYABLE')
    const existed = findTargetBySource(action, draft)
    const statusReady = ['draft', 'confirmed', 'paymentPending'].includes(draft.apStatus)
    return {
      ...draft,
      canConfirmAccountPayable: statusReady && !existed && isPositiveAmount(draft),
      accountPayableConfirmGenerated: Boolean(existed),
      sourceRejectReason: !isPositiveAmount(draft) ? '应付草稿金额为 0。' : (!statusReady ? '应付草稿状态未达成。' : (existed ? '已存在应付确认。' : '')),
    }
  })
}

function resolveSourceContext(action, options = {}) {
  if (!action) return { action: null, source: null, allowed: false, blockReasons: ['未找到当前页面动作。'] }
  let source = null
  let allowed = false
  const blockReasons = []

  if (action.actionCode === 'CREATE_PAYABLE_PREPARE') {
    source = firstEligible(getPayablePrepareSourcesFromInventory(), 'payablePrepareGenerated', 'payablePrepareGenerated')
    allowed = Boolean(source && !source.payablePrepareGenerated)
  } else if (action.actionCode === 'COMPLETE_PAYABLE_CHECK') {
    source = firstEligible(getPayableCheckSourcesFromPayablePrepares(), 'canCreatePayableCheck', 'payableCheckGenerated')
    allowed = Boolean(source?.canCreatePayableCheck)
  } else if (action.actionCode === 'CREATE_SUPPLIER_SETTLEMENT') {
    const sources = getPayableCheckSourcesForSettlement()
    const sourceQuery = options.sourceQuery || {}
    const hasExplicitContext = ['sourcePayableCheckNo', 'sourcePayablePrepareNo', 'purchaseOrderNo', 'supplierId', 'supplierName']
      .some((key) => String(sourceQuery[key] || '').trim())
    source = hasExplicitContext
      ? sources.find((item) => String(item.payableCheckNo || '').trim() === String(sourceQuery.sourcePayableCheckNo || '').trim()) || null
      : firstEligible(sources, 'canCreateSupplierSettlement', 'supplierSettlementGenerated')
    allowed = Boolean(source?.canCreateSupplierSettlement)
    if (hasExplicitContext && !source) blockReasons.push('未找到 query 指定的采购应付核对来源，不回退到其他记录。')
  } else if (action.actionCode === 'CREATE_PURCHASE_INVOICE_PREPARE') {
    blockReasons.push('V42 仅提供服务端采购对账导航资格；V43 必须重新验证 eligibility 后才能生成采购发票准备。')
  } else if (action.actionCode === 'CREATE_ACCOUNT_PAYABLE_DRAFT') {
    source = firstEligible(getApDraftSourcesFromInvoicePrepares(), 'canCreateApDraft', 'apDraftGenerated')
    allowed = Boolean(source?.canCreateApDraft)
  } else if (action.actionCode === 'CONFIRM_ACCOUNT_PAYABLE') {
    source = firstEligible(getAccountPayableDraftSourcesForConfirm(), 'canConfirmAccountPayable', 'accountPayableConfirmGenerated')
    allowed = Boolean(source?.canConfirmAccountPayable)
  } else if (action.actionCode === 'CREATE_PAYMENT_APPLICATION') {
    source = firstEligible(getPaymentApplicationSourcesFromPayableConfirms(), 'canCreatePaymentApplication', 'paymentApplicationGenerated')
    allowed = Boolean(source?.canCreatePaymentApplication)
  }

  if (!source) blockReasons.push(`当前没有可用于“${action.actionName}”的来源记录。`)
  if (source?.sourceRejectReason) blockReasons.push(source.sourceRejectReason)
  if (source && !isPositiveAmount(source) && action.actionCode !== 'CREATE_PAYABLE_PREPARE') blockReasons.push('来源金额为 0 或待补充。')

  const existingTarget = source ? findTargetBySource(action, source) : null
  if (existingTarget) {
    allowed = false
    blockReasons.push(`已存在${action.targetObjectName}：${getRecordNo(existingTarget, action.targetNoField)}。`)
  }

  return { action, source, allowed, blockReasons, existingTarget }
}

export function resolveBusinessActionContext(pageStepId, options = {}) {
  const action = findPurchasePayablePaymentActionByStepId(pageStepId)
  const context = resolveSourceContext(action, options)
  const sourceNo = getRecordNo(context.source || {}, action?.sourceNoField)
  const targetNo = getRecordNo(context.existingTarget || {}, action?.targetNoField)
  const release = evaluateNextStepRelease(action || {}, {
    targetNo,
    sourceWritebackStatus: context.source?.flowWritebackStatus || '',
    flowLinkStatus: targetNo ? 'linked' : '',
    rollbackStatus: 'not_required',
    cleanupRequired: false,
  })
  return {
    ...context,
    sourceNo,
    sourceStatus: context.source ? (context.source.payableStatus || context.source.checkStatus || context.source.settlementStatus || context.source.invoicePrepareStatus || context.source.apStatus || context.source.payableConfirmStatus || context.source.paymentApplicationStatus || context.source.status || '') : '',
    supplierName: context.source?.supplierName || '-',
    amount: getRecordAmount(context.source || {}),
    targetNo,
    release,
  }
}

function createSupplierSettlementFromPayableCheck(source) {
  const row = {
    supplierId: source.supplierId || '',
    supplierName: source.supplierName || '',
    purchaseOrderNo: source.sourcePurchaseOrderNo || source.purchaseOrderNo || '',
    receiveNo: source.sourceReceiveNo || '',
    inspectionNo: source.sourceInspectionNo || '',
    inventoryTransactionNos: source.sourceInventoryTransactionNos || [],
    payablePrepareNos: [source.sourcePayablePrepareNo].filter(Boolean),
    purchaseAmount: roundAmount(source.totalCheckedAmount || source.totalPayableAmount),
    inventoryAmount: roundAmount(source.totalCheckedAmount || source.totalPayableAmount),
    payablePrepareAmount: roundAmount(source.totalPayableAmount || source.totalCheckedAmount),
    settlementAmount: roundAmount(source.totalCheckedAmount || source.totalPayableAmount),
    differenceAmount: 0,
    reconciliationStatus: 'matched',
    settlementStatus: 'reconciled',
    differenceType: 'none',
    differenceConfirmStatus: 'not_required',
    reconciliationConfirmStatus: 'confirmed',
    nextStepReadiness: 'ready_for_invoice_prepare',
    sourceKey: `payable-check::${source.id}`,
  }
  const outcome = createSupplierSettlementDraft(row, 'page-user')
  if (!outcome.success && outcome.existed && outcome.settlement) {
    return { success: true, reused: true, target: outcome.settlement }
  }
  return { success: outcome.success, error: outcome.message, target: outcome.settlement }
}

function createAccountPayableConfirmFromDraft(source) {
  const existed = findTargetBySource(findPurchasePayablePaymentAction('CONFIRM_ACCOUNT_PAYABLE'), source)
  if (existed) return { success: true, reused: true, target: existed }
  const amount = roundAmount(source.totalPayableAmount || source.unpaidAmount || source.totalInvoiceAmount)
  const confirm = {
    id: createId('apc'),
    payableConfirmNo: createNo('APC'),
    sourceInvoicePrepareId: source.sourceInvoicePrepareId || '',
    sourceInvoicePrepareNo: source.sourceInvoicePrepareNo || '',
    sourceSettlementNo: source.sourceSettlementNo || '',
    supplierId: source.supplierId || '',
    supplierName: source.supplierName || '',
    purchaseOrderNo: source.sourcePurchaseOrderNo || '',
    invoiceNo: source.invoiceNo || '',
    invoiceDate: source.invoiceDate || '',
    invoiceType: source.invoiceType || 'specialVat',
    invoiceAmount: source.totalInvoiceAmount || amount,
    taxRate: source.taxRate || 0,
    taxAmount: source.totalTaxAmount || 0,
    totalInvoiceAmount: source.totalInvoiceAmount || amount,
    payableAmount: amount,
    confirmedPayableAmount: amount,
    currency: 'CNY',
    payableStatus: 'not_confirmed',
    payableConfirmStatus: 'draft',
    invoiceCheckStatus: 'checked',
    paymentPlanStatus: 'not_started',
    writeOffStatus: 'not_written_off',
    ledgerStatus: 'not_written_ledger',
    postingStatus: 'not_posted',
    remark: '由应付草稿生成应付确认准备；不付款、不核销、不写总账。',
    createdBy: 'page-user',
  }
  const state = getAccountPayableConfirmState()
  saveAccountPayableConfirmState({ accountPayableConfirms: [confirm, ...(state.accountPayableConfirms || [])] })
  const saved = listAccountPayableConfirms().find((item) => item.payableConfirmNo === confirm.payableConfirmNo)
  const confirmed = confirmAccountPayable(saved.id, 'page-user')
  if (!confirmed.success) return { success: false, error: confirmed.error }
  return { success: true, target: confirmed.accountPayableConfirm }
}

function performCreate(action, source) {
  if (action.actionCode === 'CREATE_PAYABLE_PREPARE') {
    const outcome = createPayablePrepareFromInventoryTransaction(source.id)
    return { success: outcome.success, error: outcome.error, target: outcome.payablePrepare }
  }
  if (action.actionCode === 'COMPLETE_PAYABLE_CHECK') {
    const outcome = createPayableCheckFromPayablePrepare(source.id)
    if (!outcome.success) return { success: false, error: outcome.error }
    const checked = markPayableCheckChecked(outcome.payableCheck.id)
    return { success: true, target: checked.payableCheck || outcome.payableCheck }
  }
  if (action.actionCode === 'CREATE_SUPPLIER_SETTLEMENT') return createSupplierSettlementFromPayableCheck(source)
  if (action.actionCode === 'CREATE_PURCHASE_INVOICE_PREPARE') {
    return { success: false, error: 'V42 禁止创建采购发票准备对象。' }
  }
  if (action.actionCode === 'GENERATE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT') {
    return {
      success: false,
      error: '正式采购应付账款草稿只能通过服务端受控生成 API 创建。',
    }
  }
  if (action.actionCode === 'CONFIRM_ACCOUNT_PAYABLE') return createAccountPayableConfirmFromDraft(source)
  if (action.actionCode === 'CREATE_PAYMENT_APPLICATION') {
    const outcome = createPaymentApplicationFromPayableConfirm(source.id, 'page-user')
    return { success: outcome.success, error: outcome.error, target: outcome.paymentApplication }
  }
  return { success: false, error: '未支持的动作。' }
}

function writeSourceAndTarget(action, source, target) {
  const sourcePatch = buildSourceWritebackPatch(action, target)
  const targetPatch = buildTargetSourcePatch(action, source)
  const sourceOutcome = patchRecord(sourceStore[action.sourceObjectType], source.id, sourcePatch)
  const targetOutcome = patchRecord(targetStore[action.targetObjectType], target.id, targetPatch)
  if (!sourceOutcome.success) throw new Error('来源状态回写失败。')
  if (!targetOutcome.success) throw new Error('目标来源关联失败。')
  return { source: sourceOutcome.record, target: targetOutcome.record }
}

export async function executeBusinessFlowAction(actionCode, options = {}) {
  const action = findPurchasePayablePaymentAction(actionCode)
  const context = resolveSourceContext(action, options)
  const source = context.source
  if (!action) return { success: false, executionStatus: 'blocked', error: '未找到动作定义。' }
  if (!source?.id) return { success: false, executionStatus: 'blocked', error: `当前没有可用于“${action.actionName}”的来源记录。` }

  const existingTarget = findTargetBySource(action, source)
  if (existingTarget) {
    const result = {
      success: true,
      executionStatus: 'already_completed_reused',
      actionCode: action.actionCode,
      actionName: action.actionName,
      sourceNo: getRecordNo(source, action.sourceNoField),
      targetNo: getRecordNo(existingTarget, action.targetNoField),
      targetCreated: false,
      originalRecordReused: true,
      duplicateProtected: true,
      sourceWritebackStatus: source.flowWritebackStatus || 'written_back',
      flowLinkStatus: 'linked',
      transactionCommitted: true,
      rollbackStatus: 'not_required',
      cleanupRequired: false,
    }
    result.nextStepRelease = evaluateNextStepRelease(action, result)
    return result
  }

  if (!context.allowed && context.blockReasons.length) {
    return { success: false, executionStatus: 'blocked', actionCode, error: context.blockReasons.join('；'), blockReasons: context.blockReasons }
  }

  return runBusinessFlowTransaction({
    participants: storeParticipants,
    operation: async () => {
      const created = performCreate(action, source)
      if (!created.success || !created.target?.id) throw new Error(created.error || `${action.targetObjectName}创建失败。`)
      if (options.forceFailureAt === 'after_target_created') throw new Error('验证触发：目标创建后失败。')
      const patched = writeSourceAndTarget(action, source, created.target)
      if (options.forceFailureAt === 'after_source_writeback') throw new Error('验证触发：来源回写后失败。')
      const sourceNo = getRecordNo(source, action.sourceNoField)
      const targetNo = getRecordNo(patched.target, action.targetNoField)
      const linkOutcome = addBusinessFlowLink({
        actionCode: action.actionCode,
        sourceObjectType: action.sourceObjectType,
        sourceObjectId: source.id,
        sourceObjectNo: sourceNo,
        targetObjectType: action.targetObjectType,
        targetObjectId: patched.target.id,
        targetObjectNo: targetNo,
      })
      if (!linkOutcome.success && !linkOutcome.existed) throw new Error('流程关联记录失败。')
      const baseResult = {
        success: true,
        executionStatus: created.reused ? 'already_completed_reused' : 'completed',
        actionCode: action.actionCode,
        actionName: action.actionName,
        sourceNo,
        targetNo,
        targetCreated: !created.reused,
        originalRecordReused: Boolean(created.reused),
        duplicateProtected: true,
        sourceWritebackStatus: 'written_back',
        flowLinkStatus: 'linked',
        transactionCommitted: true,
        rollbackStatus: 'not_required',
        cleanupRequired: false,
      }
      addBusinessFlowActionAudit({
        ...baseResult,
        sourceObjectType: action.sourceObjectType,
        targetObjectType: action.targetObjectType,
        targetObjectNo: targetNo,
      })
      baseResult.nextStepRelease = evaluateNextStepRelease(action, baseResult)
      return baseResult
    },
  })
}

export function getBusinessFlowActionDiagnostics(pageStepId) {
  const context = resolveBusinessActionContext(pageStepId)
  return {
    pageStepId,
    version: BUSINESS_FLOW_ACTION_EXECUTOR_VERSION,
    actionCode: context.action?.actionCode || '',
    actionName: context.action?.actionName || '',
    sourceNo: context.sourceNo,
    sourceStatus: context.sourceStatus,
    sourceAmount: context.amount,
    targetNo: context.targetNo,
    allowed: context.allowed,
    blockReasons: context.blockReasons,
    nextStepRelease: context.release,
    paymentApplicationTerminalNotice: context.action?.actionCode === 'CREATE_PAYMENT_APPLICATION' ? terminalPaymentApplicationNotice : '',
    protectionFlags: {
      submitOrApprove: false,
      executePayment: false,
      generateVoucher: false,
      generateFormalVoucher: false,
      writeOff: false,
      writeLedger: false,
      posting: false,
      bankFlow: false,
    },
  }
}
