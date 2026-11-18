import { findPurchasePayablePaymentActionByStepId } from './purchasePayablePaymentActionRegistry.js'
import { resolveBusinessActionContext } from './businessFlowActionExecutor.js'
import { findBusinessFlowLinkBySource } from './businessFlowLinkStore.js'
import { listBusinessFlowActionAudits } from './businessFlowActionAuditStore.js'
import { classifyTargetEvidence } from './businessTargetEvidenceClassifier.js'

export const BUSINESS_FLOW_TRANSITION_GUARD_VERSION = 'V1.14.2.7.1'

const terminalPaymentApplicationNotice = '当前版本只完成付款申请创建。付款申请审批与付款指令准备将在后续版本接入。'

const actionDisplayMap = {
  CREATE_PAYABLE_PREPARE: { targetObjectName: '采购应付预备', nextStepName: '应付核对' },
  COMPLETE_PAYABLE_CHECK: { targetObjectName: '应付核对', nextStepName: '供应商结算' },
  CREATE_SUPPLIER_SETTLEMENT: { targetObjectName: '供应商结算', nextStepName: '采购发票准备' },
  CREATE_PURCHASE_INVOICE_PREPARE: { targetObjectName: '采购发票准备', nextStepName: '应付草稿' },
  CREATE_ACCOUNT_PAYABLE_DRAFT: { targetObjectName: '应付草稿', nextStepName: '应付确认' },
  CONFIRM_ACCOUNT_PAYABLE: { targetObjectName: '应付确认', nextStepName: '付款申请' },
  CREATE_PAYMENT_APPLICATION: { targetObjectName: '付款申请', nextStepName: '付款指令准备' },
}

const stepBlockReasonMap = {
  'payable-prepare': '尚未形成有效采购应付预备，暂不能进入应付核对。',
  'payable-check': '当前应付核对尚未完成，不能进入供应商结算。',
  'supplier-settlement': '当前供应商结算尚未生成，不能进入采购发票准备。',
  'invoice-prepare': '当前采购发票准备尚未生成，不能进入应付草稿。',
  'account-payable-draft': '当前应付草稿尚未生成，不能进入应付确认。',
  'account-payable-confirm': '当前应付确认尚未完成，不能进入付款申请。',
  'payment-application': terminalPaymentApplicationNotice,
}

function hasValidIdentifier(value) {
  return typeof value === 'string' && value.trim().length > 0
}

function normalizeNo(value) {
  return hasValidIdentifier(value) ? String(value).trim() : ''
}

function condition(label, passed) {
  return { label, passed: Boolean(passed), statusText: passed ? '满足' : '未满足' }
}

function getDisplay(action = {}) {
  const local = actionDisplayMap[action.actionCode] || {}
  return {
    targetObjectName: local.targetObjectName || action.targetObjectName || '目标对象',
    nextStepName: local.nextStepName || action.nextStepName || '下一步',
  }
}

function resolveFlowEvidence(action = {}, context = {}, display = {}) {
  const source = context.source || {}
  const target = context.existingTarget || null
  const targetNo = normalizeNo(context.targetNo)
  let link = null
  let audits = []
  let evidenceReadError = null

  try {
    link = source.id
      ? findBusinessFlowLinkBySource(action.actionCode, action.sourceObjectType, source.id)
      : null
    audits = listBusinessFlowActionAudits().filter((item) => (
      item.actionCode === action.actionCode
      && item.sourceObjectNo === context.sourceNo
    ))
  } catch (error) {
    evidenceReadError = error
  }

  return classifyTargetEvidence({
    action,
    source,
    target,
    sourceNo: context.sourceNo,
    targetNo,
    link,
    audits,
    evidenceReadError,
    evidenceReadStage: 'business_flow_guard_read',
    evidenceSourceName: 'business_flow_guard',
    targetObjectLabel: display.targetObjectName,
    nextStepLabel: display.nextStepName,
  })
}

function reasonForEvidence(pageStepId, evidence, display) {
  if (evidence.targetEvidenceStatus === 'complete') {
    return `已形成${display.targetObjectName}，可以进入${display.nextStepName}。`
  }
  if (evidence.targetEvidenceStatus === 'conflict') {
    return '已发现目标记录，但目标编号、来源回写、双向关联、流程关联或事务提交证据之间存在冲突，暂不能进入下一步。'
  }
  if (evidence.targetEvidenceStatus === 'read_failed') {
    return '目标对象或关联证据读取失败，当前无法可靠确认目标状态，暂不能进入下一步。'
  }
  if (evidence.targetEvidenceStatus === 'incomplete') {
    return `已发现${display.targetObjectName}记录 ${evidence.targetNo}，但来源回写、双向关联、流程关联或事务提交证据不完整，暂不能进入${display.nextStepName}。`
  }
  return stepBlockReasonMap[pageStepId] || `尚未形成有效${display.targetObjectName}，暂不能进入${display.nextStepName}。`
}

export function evaluateBusinessFlowNextStep(pageStepId) {
  const action = findPurchasePayablePaymentActionByStepId(pageStepId)
  if (!action) {
    return {
      released: false,
      reason: '当前页面流程配置不存在，不能计算下一步。',
      conditions: [],
      evidence: { targetEvidenceStatus: 'read_failed' },
    }
  }

  const context = resolveBusinessActionContext(pageStepId)
  const display = getDisplay(action)

  if (action.actionCode === 'CREATE_PAYMENT_APPLICATION') {
    const evidence = resolveFlowEvidence(action, context, display)
    const paymentTargetValid = evidence.targetEvidenceStatus === 'complete'
    return {
      released: false,
      reason: paymentTargetValid
        ? terminalPaymentApplicationNotice
        : reasonForEvidence(pageStepId, evidence, display),
      conditions: [
        condition('付款申请已创建或已复用', paymentTargetValid),
        condition('付款申请审批与付款指令准备已接入', false),
      ],
      evidence,
    }
  }

  const evidence = resolveFlowEvidence(action, context, display)
  const conditions = [
    condition(`${display.targetObjectName}记录真实存在`, evidence.targetExists),
    condition('目标编号有效', evidence.targetNoValid),
    condition('来源状态已回写', evidence.sourceWritebackCompleted),
    condition('双向关联已完成', evidence.targetSourceLinkCompleted),
    condition('流程关联有效', evidence.flowLinkCompleted),
    condition('事务已提交', evidence.transactionCommitted),
    condition('不存在证据冲突', evidence.targetEvidenceStatus !== 'conflict'),
    condition('读取过程无异常', evidence.targetEvidenceStatus !== 'read_failed'),
    condition('无需人工清理', !evidence.cleanupRequired),
  ]
  const released = evidence.targetEvidenceStatus === 'complete' && conditions.every((item) => item.passed)

  return {
    released,
    reason: reasonForEvidence(pageStepId, evidence, display),
    conditions,
    evidence,
  }
}

