import { formatBusinessDisplayValue } from '../runtime/businessDisplayValueFormatter.js'
import { findBusinessFlowLinkBySource } from './businessFlowLinkStore.js'
import { listBusinessFlowActionAudits } from './businessFlowActionAuditStore.js'
import { classifyTargetEvidence } from './businessTargetEvidenceClassifier.js'

export const BUSINESS_ACTION_RESULT_PAGE_ADAPTER_VERSION = 'V1.14.2.7.1'

const terminalPaymentApplicationNotice = '当前版本只完成付款申请创建。付款申请审批与付款指令准备将在后续版本接入。'

const actionDisplayMap = {
  CREATE_PAYABLE_PREPARE: {
    actionName: '生成采购应付预备',
    sourceObjectLabel: '库存流水',
    targetObjectLabel: '采购应付预备',
    nextStepLabel: '应付核对',
  },
  COMPLETE_PAYABLE_CHECK: {
    actionName: '完成应付核对',
    sourceObjectLabel: '采购应付预备',
    targetObjectLabel: '应付核对',
    nextStepLabel: '供应商结算',
  },
  CREATE_SUPPLIER_SETTLEMENT: {
    actionName: '生成供应商结算',
    sourceObjectLabel: '应付核对',
    targetObjectLabel: '供应商结算',
    nextStepLabel: '采购发票准备',
  },
  CREATE_PURCHASE_INVOICE_PREPARE: {
    actionName: '生成采购发票准备',
    sourceObjectLabel: '供应商结算',
    targetObjectLabel: '采购发票准备',
    nextStepLabel: '应付草稿',
  },
  CREATE_ACCOUNT_PAYABLE_DRAFT: {
    actionName: '生成应付草稿',
    sourceObjectLabel: '采购发票准备',
    targetObjectLabel: '应付草稿',
    nextStepLabel: '应付确认',
  },
  CONFIRM_ACCOUNT_PAYABLE: {
    actionName: '确认应付',
    sourceObjectLabel: '应付草稿',
    targetObjectLabel: '应付确认',
    nextStepLabel: '付款申请',
  },
  CREATE_PAYMENT_APPLICATION: {
    actionName: '生成付款申请',
    sourceObjectLabel: '应付确认',
    targetObjectLabel: '付款申请',
    nextStepLabel: '付款指令准备',
  },
}

function getActionDisplay(action = {}) {
  const local = actionDisplayMap[action.actionCode] || {}
  return {
    actionName: local.actionName || action.actionName || '未接入真实业务动作',
    sourceObjectLabel: local.sourceObjectLabel || action.sourceObjectName || '来源对象',
    targetObjectLabel: local.targetObjectLabel || action.targetObjectName || '目标对象',
    nextStepLabel: local.nextStepLabel || action.nextStepName || '下一步',
  }
}

function value(rawValue, displayType, fallback) {
  return formatBusinessDisplayValue(rawValue, { displayType, fallback })
}

function hasValidIdentifier(identifier) {
  return typeof identifier === 'string' && identifier.trim().length > 0
}

function normalizeNo(identifier) {
  return hasValidIdentifier(identifier) ? String(identifier).trim() : ''
}

function clone(value) {
  return JSON.parse(JSON.stringify(value ?? null))
}

function buildFixtureEvidenceInput(context = {}, actionDisplay = {}) {
  const fixture = context.targetEvidenceFixture || ''
  if (!fixture) return null
  const action = context.action || {}
  const baseSource = {
    ...(clone(context.source) || {}),
    id: context.source?.id || 'fixture-source-id',
  }
  const sourceNo = normalizeNo(context.sourceNo) || 'FIXTURE-SOURCE-001'
  const targetNo = normalizeNo(context.targetNo)
    || (action.actionCode === 'CREATE_PAYABLE_PREPARE' ? 'PP-FIXTURE-001' : 'TARGET-FIXTURE-001')

  if (fixture === 'not_found') {
    return {
      action,
      source: baseSource,
      target: null,
      sourceNo,
      targetNo: '',
      targetObjectLabel: actionDisplay.targetObjectLabel,
      nextStepLabel: actionDisplay.nextStepLabel,
    }
  }

  if (fixture === 'complete') {
    const target = {
      id: 'fixture-target-complete',
      [action.targetNoField || 'targetNo']: targetNo,
      sourceLinkStatus: 'linked',
      sourceObjectType: action.sourceObjectType,
      sourceObjectId: baseSource.id,
    }
    return {
      action,
      source: { ...baseSource, flowWritebackStatus: 'written_back' },
      target,
      sourceNo,
      targetNo,
      link: { targetObjectNo: targetNo, linkStatus: 'linked' },
      audits: [{ targetObjectNo: targetNo, executionStatus: 'committed', cleanupRequired: false }],
      targetObjectLabel: actionDisplay.targetObjectLabel,
      nextStepLabel: actionDisplay.nextStepLabel,
    }
  }

  if (fixture === 'incomplete') {
    const target = {
      id: 'fixture-target-incomplete',
      [action.targetNoField || 'targetNo']: targetNo,
      sourceObjectType: action.sourceObjectType,
      sourceObjectId: baseSource.id,
    }
    return {
      action,
      source: { ...baseSource, flowWritebackStatus: '' },
      target,
      sourceNo,
      targetNo,
      targetObjectLabel: actionDisplay.targetObjectLabel,
      nextStepLabel: actionDisplay.nextStepLabel,
    }
  }

  if (fixture === 'conflict') {
    const conflictNo = `${targetNo}-CONFLICT`
    const target = {
      id: 'fixture-target-conflict',
      [action.targetNoField || 'targetNo']: targetNo,
      sourceLinkStatus: 'linked',
      sourceObjectType: action.sourceObjectType,
      sourceObjectId: `${baseSource.id}-other`,
    }
    return {
      action,
      source: { ...baseSource, flowWritebackStatus: 'written_back' },
      target,
      sourceNo,
      targetNo,
      link: { targetObjectNo: conflictNo, linkStatus: 'linked' },
      audits: [{ targetObjectNo: `${targetNo}-AUDIT`, executionStatus: 'committed', cleanupRequired: false }],
      candidateTargets: [
        { id: 'fixture-target-conflict', targetObjectNo: targetNo },
        { id: 'fixture-target-conflict-2', targetObjectNo: conflictNo },
      ],
      targetObjectLabel: actionDisplay.targetObjectLabel,
      nextStepLabel: actionDisplay.nextStepLabel,
    }
  }

  if (fixture === 'read_failed') {
    const target = {
      id: 'fixture-target-read-failed',
      [action.targetNoField || 'targetNo']: targetNo,
      sourceObjectType: action.sourceObjectType,
      sourceObjectId: baseSource.id,
    }
    return {
      action,
      source: { ...baseSource, flowWritebackStatus: 'written_back' },
      target,
      sourceNo,
      targetNo,
      evidenceReadError: new Error('fixture evidence read failed'),
      evidenceReadStage: 'fixture_evidence_read',
      evidenceSourceName: 'read_only_fixture',
      targetObjectLabel: actionDisplay.targetObjectLabel,
      nextStepLabel: actionDisplay.nextStepLabel,
    }
  }

  return null
}

function resolveTargetEvidence(context = {}, actionDisplay = {}) {
  const fixtureInput = buildFixtureEvidenceInput(context, actionDisplay)
  if (fixtureInput) return classifyTargetEvidence(fixtureInput)

  const action = context.action || {}
  const source = context.source || {}
  const target = context.existingTarget || null
  const targetNo = normalizeNo(context.targetNo)
  let link = null
  let audits = []
  let evidenceReadError = null

  try {
    link = source?.id
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
    evidenceReadStage: 'business_flow_link_or_audit_read',
    evidenceSourceName: 'business_flow_link_store_and_audit_store',
    targetObjectLabel: actionDisplay.targetObjectLabel,
    nextStepLabel: actionDisplay.nextStepLabel,
  })
}

function buildRecoveredResult(targetEvidence) {
  const status = targetEvidence.targetEvidenceStatus
  if (status === 'complete') {
    return {
      success: true,
      executionStatus: 'existing_target_complete',
      targetCreated: false,
      originalRecordReused: true,
      targetNo: targetEvidence.targetNo,
      sourceWritebackStatus: 'written_back',
      flowLinkStatus: targetEvidence.flowLinkStatus || 'linked',
      transactionCommitted: true,
      rollbackStatus: 'not_required',
      cleanupRequired: false,
      resultSource: '已存在且关联完整的业务处理结果',
      historyEvidence: targetEvidence,
    }
  }
  if (status === 'incomplete') {
    return {
      success: false,
      executionStatus: 'existing_target_incomplete',
      targetCreated: false,
      originalRecordReused: true,
      targetNo: targetEvidence.targetNo,
      sourceWritebackStatus: targetEvidence.sourceWritebackCompleted ? 'written_back' : '',
      flowLinkStatus: targetEvidence.flowLinkStatus || '',
      transactionCommitted: targetEvidence.transactionCommitted,
      rollbackStatus: 'not_required',
      cleanupRequired: targetEvidence.cleanupRequired,
      resultSource: '已存在目标，但关联证据不完整',
      historyEvidence: targetEvidence,
    }
  }
  if (status === 'conflict') {
    return {
      success: false,
      executionStatus: 'existing_target_conflict',
      targetCreated: false,
      originalRecordReused: true,
      targetNo: targetEvidence.targetNo,
      sourceWritebackStatus: targetEvidence.sourceWritebackCompleted ? 'written_back' : '',
      flowLinkStatus: targetEvidence.flowLinkStatus || '',
      transactionCommitted: targetEvidence.transactionCommitted,
      rollbackStatus: 'not_required',
      cleanupRequired: targetEvidence.cleanupRequired,
      resultSource: '已发现目标关联冲突',
      historyEvidence: targetEvidence,
    }
  }
  if (status === 'read_failed') {
    return {
      success: false,
      executionStatus: 'target_evidence_read_failed',
      targetCreated: false,
      originalRecordReused: false,
      targetNo: targetEvidence.targetNo,
      sourceWritebackStatus: '',
      flowLinkStatus: '',
      transactionCommitted: false,
      rollbackStatus: 'not_required',
      cleanupRequired: false,
      resultSource: '目标证据读取失败',
      historyEvidence: targetEvidence,
      readFailed: true,
    }
  }
  return {
    success: false,
    executionStatus: 'target_not_found',
    targetCreated: false,
    originalRecordReused: false,
    targetNo: '',
    sourceWritebackStatus: '',
    flowLinkStatus: '',
    transactionCommitted: false,
    rollbackStatus: 'not_required',
    cleanupRequired: false,
    resultSource: '尚未发现目标记录',
    historyEvidence: targetEvidence,
  }
}

function resolveResultSource(hasSessionResult, recoveredResult) {
  if (hasSessionResult) return '本次页面会话执行结果'
  if (recoveredResult?.resultSource) return recoveredResult.resultSource
  return '尚未执行'
}

function statusSpecificMessage(targetEvidence) {
  if (targetEvidence.targetEvidenceStatus === 'complete') {
    return '已发现目标记录，关联证据完整；是否进入下一步仍需满足既有业务放行条件。'
  }
  if (targetEvidence.targetEvidenceStatus === 'incomplete') {
    return '已发现目标记录，但处理证据不完整，请先核对来源回写、双向关联、流程关联和事务提交证据。'
  }
  if (targetEvidence.targetEvidenceStatus === 'conflict') {
    return '已发现目标关联冲突，请人工核对目标编号、来源回写、双向关联、流程关联和事务提交证据。'
  }
  if (targetEvidence.targetEvidenceStatus === 'read_failed') {
    return '目标对象或关联证据读取失败，当前无法可靠确认目标状态。'
  }
  return '未发现目标对象，本轮页面会话尚未执行业务动作。'
}

export function adaptBusinessActionResultToPage({ context = {}, latestResult = {}, nextStepRelease = {} }) {
  const action = context.action || {}
  const actionDisplay = getActionDisplay(action)
  const targetEvidence = resolveTargetEvidence(context, actionDisplay)
  const hasSessionResult = Boolean(latestResult && latestResult.executionStatus)
  const recoveredResult = hasSessionResult ? null : buildRecoveredResult(targetEvidence)
  const result = hasSessionResult ? latestResult : recoveredResult
  const hasAnyResult = Boolean(result)
  const currentFlowClosureCompleted = (
    targetEvidence.targetEvidenceStatus === 'complete'
    || (hasAnyResult && result.executionStatus === 'completed' && hasValidIdentifier(result.targetNo))
  )
  const nextStepAllowed = targetEvidence.targetEvidenceStatus === 'complete'
    ? Boolean(nextStepRelease.released)
    : false
  const nextReason = targetEvidence.targetEvidenceStatus === 'complete'
    ? (nextStepRelease.reason || '当前无阻断原因。')
    : targetEvidence.nextStepBlockingReason
  const resultSource = resolveResultSource(hasSessionResult, recoveredResult)

  return {
    actionPanelTitle: '真实业务动作与状态回写',
    resultPanelTitle: '本次动作结果',
    resultSourceText: value(resultSource, 'text'),
    currentActionName: value(actionDisplay.actionName, 'text'),
    actionButtonText: '执行本步业务动作',
    sourceObjectLabel: value(actionDisplay.sourceObjectLabel, 'text'),
    targetObjectLabel: value(actionDisplay.targetObjectLabel, 'text'),
    sourceObjectNoText: value(context.sourceNo, 'identifier', '来源不存在'),
    sourceStatusText: value(context.sourceStatus, 'status', context.sourceNo ? '不适用' : '来源不存在'),
    actionAllowedText: value(context.allowed, 'boolean', '否'),
    actionBlockReasonText: value(context.blockReasons, 'reason'),
    actionCompletedText: value(hasValidIdentifier(context.targetNo), 'boolean'),
    existingTargetNoText: value(context.targetNo, 'identifier'),

    executionStatusText: hasAnyResult ? value(result.executionStatus, 'status') : value('not_executed', 'status'),
    executionStatusRaw: result?.executionStatus || '',
    targetCreatedText: hasAnyResult ? value(result.targetCreated, 'boolean') : value(null, 'boolean', '未执行'),
    existingTargetReusedText: hasAnyResult ? value(result.originalRecordReused, 'boolean') : value(null, 'boolean', '未执行'),
    targetObjectNoText: value(targetEvidence.targetObjectNoDisplay, 'identifier', targetEvidence.targetObjectNoDisplay),
    targetObjectNoRaw: targetEvidence.targetObjectNoRaw,
    targetObjectExistsText: value(targetEvidence.targetExists, 'boolean'),
    targetEvidenceStatus: targetEvidence.targetEvidenceStatus,
    targetEvidenceStatusText: value(targetEvidence.targetEvidenceStatus, 'evidenceStatus'),
    targetEvidenceStatusLabel: targetEvidence.targetEvidenceStatusLabel,
    targetEvidenceStatusReason: targetEvidence.targetEvidenceStatusReason,
    missingEvidenceCodes: targetEvidence.missingEvidenceCodes,
    missingEvidenceTexts: targetEvidence.missingEvidenceTexts,
    targetEvidenceMissingItems: targetEvidence.targetEvidenceMissingItems,
    targetEvidenceConflictItems: targetEvidence.targetEvidenceConflictItems,
    targetEvidenceReadFailures: targetEvidence.targetEvidenceReadFailures,
    targetEvidenceClassificationPassed: targetEvidence.targetEvidenceClassificationPassed,
    targetEvidenceClassificationFailures: targetEvidence.targetEvidenceClassificationFailures,
    targetEvidenceTraceItems: targetEvidence.targetEvidenceTraceItems || [],
    targetEvidenceTracePassedCount: targetEvidence.targetEvidenceTracePassedCount || 0,
    targetEvidenceTraceFailedCount: targetEvidence.targetEvidenceTraceFailedCount || 0,
    targetEvidenceTraceBlockingCount: targetEvidence.targetEvidenceTraceBlockingCount || 0,
    targetEvidenceTraceCoveragePassed: Boolean(targetEvidence.targetEvidenceTraceCoveragePassed),
    targetEvidenceTraceCoverageFailures: targetEvidence.targetEvidenceTraceCoverageFailures || [],
    targetEvidenceFirstFailureCode: targetEvidence.targetEvidenceFirstFailureCode || '',
    targetEvidenceFirstFailureLabel: targetEvidence.targetEvidenceFirstFailureLabel || '未发现异常',
    targetEvidenceFirstFailureCategory: targetEvidence.targetEvidenceFirstFailureCategory || '',
    targetEvidenceFirstFailureReason: targetEvidence.targetEvidenceFirstFailureReason || '未发现异常',
    targetEvidenceFirstFailureResponsibility: targetEvidence.targetEvidenceFirstFailureResponsibility || 'unknown',
    targetEvidenceFirstFailureResponsibilityLabel: targetEvidence.targetEvidenceFirstFailureResponsibilityLabel || '暂无定位',
    targetEvidenceFirstFailureBlocking: Boolean(targetEvidence.targetEvidenceFirstFailureBlocking),
    targetEvidenceResponsibilitySummary: targetEvidence.targetEvidenceResponsibilitySummary || [],
    targetEvidenceSourceConsistencyPassed: Boolean(targetEvidence.targetEvidenceSourceConsistencyPassed),
    targetEvidenceSourceConsistencyFailures: targetEvidence.targetEvidenceSourceConsistencyFailures || [],
    missingEvidenceSummaryText: targetEvidence.missingEvidenceTexts.length
      ? targetEvidence.missingEvidenceTexts.join('；')
      : '无缺失证据',
    sourceWritebackText: value(targetEvidence.sourceWritebackCompleted, 'boolean'),
    bidirectionalLinkText: value(targetEvidence.targetSourceLinkCompleted, 'boolean'),
    transactionCommittedText: value(targetEvidence.transactionCommitted, 'boolean'),
    rollbackExecutedText: hasAnyResult ? value(result.rollbackStatus === 'rolled_back', 'boolean') : value(null, 'boolean', '未执行'),
    cleanupRequiredText: value(targetEvidence.cleanupRequired, 'boolean'),
    nextStepReleasedText: value(nextStepAllowed, 'boolean', '否'),
    nextStepAllowed,
    nextStepBlockingReason: nextReason,
    resultMessageText: value(statusSpecificMessage(targetEvidence), 'text'),

    currentFlowClosureCompletedText: value(currentFlowClosureCompleted, 'boolean', '否'),
    businessClosureCompletedText: value(currentFlowClosureCompleted, 'boolean', '否'),
    nextBusinessStepReleasedText: value(nextStepAllowed, 'boolean', '否'),
    nextBusinessStepBlockReasonText: value(
      action.actionCode === 'CREATE_PAYMENT_APPLICATION' && targetEvidence.targetEvidenceStatus === 'complete'
        ? terminalPaymentApplicationNotice
        : nextReason,
      'reason',
    ),
    nextStepConditions: Array.isArray(nextStepRelease.conditions) ? nextStepRelease.conditions : [],
    isPaymentApplication: action.actionCode === 'CREATE_PAYMENT_APPLICATION',
    terminalPaymentApplicationNotice,
    historyEvidence: recoveredResult?.historyEvidence || targetEvidence,
  }
}
