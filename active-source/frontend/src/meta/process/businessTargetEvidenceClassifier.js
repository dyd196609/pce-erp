export const BUSINESS_TARGET_EVIDENCE_CLASSIFIER_VERSION = 'V1.14.2.7.1'

export const targetEvidenceStatusPriority = [
  'read_failed',
  'conflict',
  'complete',
  'incomplete',
  'not_found',
]

const statusLabelMap = {
  not_found: '未发现目标对象',
  complete: '完整',
  incomplete: '不完整',
  conflict: '冲突',
  read_failed: '读取失败',
}

const statusReasonMap = {
  not_found: '目标对象读取成功，可以确认目标记录不存在。',
  complete: '目标对象存在，来源回写、反向关联、流程关联、事务提交和状态回写证据完整。',
  incomplete: '已发现目标记录，但至少一项必要证据缺失。',
  conflict: '已发现目标记录，但目标编号、来源回写、反向关联、流程关联或事务证据之间存在冲突。',
  read_failed: '目标对象或关联证据读取失败，当前无法可靠确认目标状态。',
}

const missingEvidenceLabelMap = {
  source_writeback_missing: '来源状态尚未回写',
  target_source_link_missing: '目标反向来源关联尚未完成',
  flow_link_missing: '流程关联记录尚未建立或未指向当前目标',
  transaction_commit_missing: '事务提交证据不存在',
  status_writeback_missing: '状态回写证据不完整',
  cleanup_required: '存在需要人工清理的执行痕迹',
  target_number_missing: '目标编号缺失',
}

const evidenceCategoryLabelMap = {
  source_object: '来源业务对象',
  target_object: '目标业务对象',
  source_writeback: '来源回写证据',
  reverse_link: '目标反向关联证据',
  process_link: '流程实例关联证据',
  transaction_commit: '事务提交证据',
  status_writeback: '状态回写证据',
  uniqueness: '候选目标唯一性证据',
  read_integrity: '数据读取与解析证据',
}

const responsibilityLabelMap = {
  source_business_data: '来源业务数据',
  target_business_data: '目标业务数据',
  relation_writeback: '关联回写',
  process_runtime: '流程运行数据',
  transaction_evidence: '事务提交证据',
  status_writeback: '状态回写',
  duplicate_target: '重复目标对象',
  data_format: '数据格式',
  read_runtime: '运行时读取',
  unknown: '暂无定位',
}

const failureResponsibilityMap = {
  source_read_failed: 'read_runtime',
  target_read_failed: 'read_runtime',
  evidence_read_failed: 'read_runtime',
  data_format_invalid: 'data_format',
  target_not_found: 'target_business_data',
  target_number_missing: 'target_business_data',
  missing_source_writeback: 'relation_writeback',
  missing_reverse_link: 'relation_writeback',
  missing_process_link: 'process_runtime',
  missing_transaction_commit: 'transaction_evidence',
  missing_status_writeback: 'status_writeback',
  target_number_mismatch: 'process_runtime',
  source_number_mismatch: 'target_business_data',
  multiple_target_candidates: 'duplicate_target',
  cleanup_required: 'transaction_evidence',
  unknown_failure: 'unknown',
}

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function clone(value) {
  return JSON.parse(JSON.stringify(value ?? null))
}

function hasValidIdentifier(value) {
  return typeof value === 'string' && value.trim().length > 0
}

function normalizeNo(value) {
  return hasValidIdentifier(value) ? String(value).trim() : ''
}

function valueToText(value, fallback = '空') {
  if (value === null || value === undefined || value === '') return fallback
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (Array.isArray(value)) return value.length ? value.map((item) => valueToText(item, '')).filter(Boolean).join('、') : fallback
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch (error) {
      return '[不可序列化对象]'
    }
  }
  return String(value)
}

function safeString(value, fallback = '空') {
  return valueToText(value, fallback)
}

function dedupeItems(items = [], keyBuilder) {
  const seen = new Set()
  return items.filter((item) => {
    const key = keyBuilder(item)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function normalizeCandidateTargets(candidates = [], targetNoField = '') {
  if (!Array.isArray(candidates)) return []
  return dedupeItems(candidates
    .filter(Boolean)
    .map((item) => {
      const targetNo = normalizeNo(item.targetObjectNo || item.targetNo || item[targetNoField] || item.no)
      return {
        id: safeString(item.id || '', ''),
        targetNo,
      }
    })
    .filter((item) => item.id || item.targetNo), (item) => `${item.id}::${item.targetNo}`)
}

function resolveAuditTargetNo(audit = {}, targetNoField = '') {
  return normalizeNo(
    audit.targetObjectNo
    || audit.targetNo
    || audit[targetNoField]
    || '',
  )
}

function buildReadFailure({
  code,
  readStage,
  dataSource,
  error,
  errorType = 'read_error',
  fallbackUsed = false,
  affectsTargetExistence = true,
}) {
  const message = error?.message || error?.name || safeString(error, '读取失败')
  return {
    code,
    readStage,
    dataSource,
    errorType,
    safeErrorSummary: message.slice(0, 180),
    fallbackUsed: Boolean(fallbackUsed),
    affectsTargetExistence: Boolean(affectsTargetExistence),
  }
}

function buildMissingItem(code, traceItem) {
  return {
    code,
    label: missingEvidenceLabelMap[code] || traceItem?.evidenceLabel || code,
    evidenceSource: traceItem?.sourceModule || traceItem?.evidenceCategory || 'runtime',
    affectsNextStep: true,
    sourceObjectType: traceItem?.sourceObjectType || '',
    sourceObjectNo: traceItem?.sourceObjectNo || '',
    sourceField: traceItem?.sourceField || '',
    expectedRelation: traceItem?.expectedRelation || '',
    actualRelation: traceItem?.actualRelation || '',
    responsibilityCategory: traceItem?.responsibilityCategory || 'unknown',
  }
}

function buildConflictItem({
  code,
  conflictType,
  rawValue,
  compareValue,
  evidenceSource,
  description,
  traceItem,
}) {
  return {
    code,
    conflictType,
    rawValue: safeString(rawValue),
    compareValue: safeString(compareValue),
    evidenceSource,
    affectsNextStep: true,
    description,
    traceCode: traceItem?.evidenceCode || '',
    sourceObjectType: traceItem?.sourceObjectType || '',
    sourceObjectNo: traceItem?.sourceObjectNo || '',
    sourceField: traceItem?.sourceField || '',
    targetObjectType: traceItem?.targetObjectType || '',
    targetObjectNo: traceItem?.targetObjectNo || '',
    targetField: traceItem?.targetField || '',
    responsibilityCategory: traceItem?.responsibilityCategory || 'unknown',
  }
}

function evidenceItem(input = {}) {
  const failureType = input.failureType || ''
  const responsibilityCategory = input.responsibilityCategory
    || failureResponsibilityMap[failureType]
    || 'unknown'
  const status = input.evidenceStatus || 'passed'
  const blocking = input.blocking ?? ['missing', 'conflict', 'read_failed'].includes(status)
  const evidenceCode = input.evidenceCode
  const evidenceCategory = input.evidenceCategory
  return {
    evidenceCode,
    evidenceLabel: input.evidenceLabel || evidenceCode,
    evidenceCategory,
    evidenceCategoryLabel: evidenceCategoryLabelMap[evidenceCategory] || evidenceCategory,
    sourceModule: input.sourceModule || '',
    sourceObjectType: input.sourceObjectType || '',
    sourceObjectNo: valueToText(input.sourceObjectNo, ''),
    sourceField: input.sourceField || '',
    sourceValue: valueToText(input.sourceValue),
    targetModule: input.targetModule || '',
    targetObjectType: input.targetObjectType || '',
    targetObjectNo: valueToText(input.targetObjectNo, ''),
    targetField: input.targetField || '',
    targetValue: valueToText(input.targetValue),
    expectedRelation: input.expectedRelation || '',
    actualRelation: input.actualRelation || '',
    evidenceStatus: status,
    evidenceStatusLabel: {
      passed: '通过',
      missing: '缺失',
      conflict: '冲突',
      read_failed: '读取失败',
      not_applicable: '不适用',
    }[status] || status,
    failureType,
    failureReason: input.failureReason || '',
    blocking,
    firstFailure: false,
    responsibilityCategory,
    responsibilityLabel: responsibilityLabelMap[responsibilityCategory] || responsibilityCategory,
    sourceReadable: input.sourceReadable !== false,
    deterministicTraceKey: [
      'targetEvidenceTrace',
      evidenceCategory,
      evidenceCode,
      input.sourceObjectType || '',
      input.targetObjectType || '',
    ].join(':'),
  }
}

function resolveStatusOutput({
  targetExists,
  targetNo,
  readFailures,
  conflictItems,
  missingItems,
}) {
  let targetEvidenceStatus = 'not_found'
  if (readFailures.length > 0) {
    targetEvidenceStatus = 'read_failed'
  } else if (conflictItems.length > 0) {
    targetEvidenceStatus = 'conflict'
  } else if (targetExists && hasValidIdentifier(targetNo) && missingItems.length === 0) {
    targetEvidenceStatus = 'complete'
  } else if (targetExists && hasValidIdentifier(targetNo)) {
    targetEvidenceStatus = 'incomplete'
  }

  return {
    targetEvidenceStatus,
    targetEvidenceStatusLabel: statusLabelMap[targetEvidenceStatus],
    targetEvidenceStatusReason: statusReasonMap[targetEvidenceStatus],
  }
}

function resolveNextStepBlockReason(status, targetObjectLabel = '目标对象', nextStepLabel = '下一步') {
  if (status === 'complete') return '目标证据完整，是否进入下一步仍需满足现有业务放行条件。'
  if (status === 'conflict') {
    return '已发现目标记录，但目标编号、来源回写、反向关联、流程关联或事务提交证据之间存在冲突，暂不能进入下一步。'
  }
  if (status === 'read_failed') {
    return '目标对象或关联证据读取失败，当前无法可靠确认目标状态，暂不能进入下一步。'
  }
  if (status === 'incomplete') {
    return `已发现${targetObjectLabel}记录，但来源回写、反向关联、流程关联、事务提交或状态回写证据不完整，暂不能进入${nextStepLabel}。`
  }
  return `尚未发现有效${targetObjectLabel}记录，暂不能进入${nextStepLabel}。`
}

function firstFailureForStatus(status, traceItems) {
  if (status === 'complete') {
    return {
      targetEvidenceFirstFailureCode: '',
      targetEvidenceFirstFailureLabel: '未发现异常',
      targetEvidenceFirstFailureCategory: '',
      targetEvidenceFirstFailureReason: '目标证据来源链未发现异常。',
      targetEvidenceFirstFailureResponsibility: 'unknown',
      targetEvidenceFirstFailureResponsibilityLabel: responsibilityLabelMap.unknown,
      targetEvidenceFirstFailureBlocking: false,
    }
  }

  const expectedStatus = {
    not_found: 'missing',
    incomplete: 'missing',
    conflict: 'conflict',
    read_failed: 'read_failed',
  }[status]
  const item = traceItems.find((traceItem) => traceItem.evidenceStatus === expectedStatus)
    || traceItems.find((traceItem) => traceItem.blocking)
  return {
    targetEvidenceFirstFailureCode: item?.evidenceCode || '',
    targetEvidenceFirstFailureLabel: item?.evidenceLabel || '未发现异常',
    targetEvidenceFirstFailureCategory: item?.evidenceCategory || '',
    targetEvidenceFirstFailureReason: item?.failureReason || '未发现异常',
    targetEvidenceFirstFailureResponsibility: item?.responsibilityCategory || 'unknown',
    targetEvidenceFirstFailureResponsibilityLabel: item?.responsibilityLabel || responsibilityLabelMap.unknown,
    targetEvidenceFirstFailureBlocking: Boolean(item?.blocking),
  }
}

function summarizeResponsibility(traceItems) {
  return Object.values(traceItems
    .filter((item) => item.blocking)
    .reduce((summary, item) => {
      const key = item.responsibilityCategory || 'unknown'
      if (!summary[key]) {
        summary[key] = {
          responsibilityCategory: key,
          responsibilityLabel: responsibilityLabelMap[key] || key,
          count: 0,
          blockingCount: 0,
          evidenceCodes: [],
        }
      }
      summary[key].count += 1
      if (item.blocking) summary[key].blockingCount += 1
      summary[key].evidenceCodes.push(item.evidenceCode)
      return summary
    }, {}))
}

function resolveTraceCoverage(traceItems) {
  const requiredCategories = [
    'source_object',
    'target_object',
    'source_writeback',
    'reverse_link',
    'process_link',
    'transaction_commit',
    'status_writeback',
    'uniqueness',
    'read_integrity',
  ]
  const categories = new Set(traceItems.map((item) => item.evidenceCategory))
  const failures = requiredCategories
    .filter((category) => !categories.has(category))
    .map((category) => `missing_category:${category}`)
  const keySet = new Set(traceItems.map((item) => item.deterministicTraceKey))
  if (keySet.size !== traceItems.length) failures.push('duplicate_deterministic_trace_key')
  return {
    targetEvidenceTraceCoveragePassed: failures.length === 0,
    targetEvidenceTraceCoverageFailures: failures,
  }
}

function resolveSourceConsistency({
  traceItems,
  missingItems,
  conflictItems,
  readFailures,
}) {
  const failures = []
  const missingTraceCodes = new Set(traceItems.filter((item) => item.evidenceStatus === 'missing').map((item) => item.evidenceCode))
  const conflictTraceCodes = new Set(traceItems.filter((item) => item.evidenceStatus === 'conflict').map((item) => item.evidenceCode))
  const readFailureTraceCodes = new Set(traceItems.filter((item) => item.evidenceStatus === 'read_failed').map((item) => item.evidenceCode))
  for (const item of missingItems) {
    if (!missingTraceCodes.has(item.code) && !conflictTraceCodes.has(item.code)) failures.push(`missing_item_without_trace:${item.code}`)
  }
  for (const item of conflictItems) {
    if (!conflictTraceCodes.has(item.code) && !conflictTraceCodes.has(item.traceCode)) failures.push(`conflict_item_without_trace:${item.code}`)
  }
  for (const item of readFailures) {
    if (!readFailureTraceCodes.has(item.code)) failures.push(`read_failure_without_trace:${item.code}`)
  }
  return {
    targetEvidenceSourceConsistencyPassed: failures.length === 0,
    targetEvidenceSourceConsistencyFailures: failures,
  }
}

function statusWritebackComplete(input, targetExists) {
  if (!targetExists) return false
  if (input.statusWritebackCompleted === false) return false
  return true
}

export function classifyTargetEvidence(input = {}) {
  const snapshot = clone(input)
  const action = input.action || {}
  const source = isPlainObject(input.source) ? input.source : {}
  const target = isPlainObject(input.target) ? input.target : {}
  const rawTarget = input.target
  const link = input.link || null
  const audits = Array.isArray(input.audits) ? input.audits : []
  const targetNoField = action.targetNoField || input.targetNoField || ''
  const sourceNo = normalizeNo(
    input.sourceNo
    || source.sourceObjectNo
    || source.no
    || source[action.sourceNoField || '']
    || '',
  )
  const targetNo = normalizeNo(
    input.targetNo
    || target.targetObjectNo
    || target.targetNo
    || target[targetNoField]
    || '',
  )
  const targetExists = Boolean(target?.id || targetNo)
  const targetObjectReadable = Boolean(
    target
    && (
      target.id
      || target.targetObjectNo
      || target.targetNo
      || target[targetNoField]
    ),
  )
  const targetNoValid = hasValidIdentifier(targetNo)
  const linkTargetNo = normalizeNo(link?.targetObjectNo || link?.targetNo || '')
  const flowLinkStatus = link?.linkStatus || ''
  const auditTargetNos = dedupeItems(
    audits.map((audit) => resolveAuditTargetNo(audit, targetNoField)).filter(Boolean).map((value) => ({ value })),
    (item) => item.value,
  ).map((item) => item.value)
  const committedAudit = audits.find((audit) => ['completed', 'already_completed_reused', 'committed'].includes(audit?.executionStatus))
  const cleanupRequired = audits.some((audit) => Boolean(audit?.cleanupRequired))
  const candidateTargets = normalizeCandidateTargets(input.candidateTargets, targetNoField)
  const targetObjectLabel = input.targetObjectLabel || action.targetObjectName || action.targetObjectType || '目标对象'
  const nextStepLabel = input.nextStepLabel || action.nextStepName || '下一步'
  const sourceObjectType = action.sourceObjectType || 'source_object'
  const targetObjectType = action.targetObjectType || 'target_object'
  const traceItems = []
  const readFailures = []

  function pushTrace(item) {
    const traceItem = evidenceItem({
      sourceObjectType,
      targetObjectType,
      sourceObjectNo: sourceNo,
      targetObjectNo: targetNo,
      sourceModule: sourceObjectType,
      targetModule: targetObjectType,
      ...item,
    })
    traceItems.push(traceItem)
    return traceItem
  }

  if (input.sourceReadError) {
    const failure = buildReadFailure({
      code: 'source_read_failed',
      readStage: input.sourceReadStage || 'source_object_read',
      dataSource: input.sourceReadSource || sourceObjectType,
      error: input.sourceReadError,
      affectsTargetExistence: true,
    })
    readFailures.push(failure)
    pushTrace({
      evidenceCode: 'source_read_failed',
      evidenceLabel: '来源业务对象读取失败',
      evidenceCategory: 'source_object',
      sourceField: action.sourceNoField || 'sourceObjectNo',
      sourceValue: sourceNo,
      expectedRelation: '来源对象必须可读取',
      actualRelation: failure.safeErrorSummary,
      evidenceStatus: 'read_failed',
      failureType: 'source_read_failed',
      failureReason: failure.safeErrorSummary,
      responsibilityCategory: 'read_runtime',
      sourceReadable: false,
    })
  } else {
    pushTrace({
      evidenceCode: 'source_object_readable',
      evidenceLabel: '来源业务对象可读取',
      evidenceCategory: 'source_object',
      sourceField: action.sourceNoField || 'sourceObjectNo',
      sourceValue: sourceNo,
      expectedRelation: '来源对象存在且可读取',
      actualRelation: sourceNo ? `来源编号 ${sourceNo}` : '来源编号为空',
      evidenceStatus: sourceNo ? 'passed' : 'missing',
      failureType: sourceNo ? '' : 'unknown_failure',
      failureReason: sourceNo ? '' : '来源业务对象编号缺失。',
      responsibilityCategory: sourceNo ? 'source_business_data' : 'source_business_data',
      blocking: !sourceNo,
    })
  }

  if (input.targetReadError) {
    const failure = buildReadFailure({
      code: 'target_read_failed',
      readStage: input.targetReadStage || 'target_object_read',
      dataSource: input.targetReadSource || targetObjectType,
      error: input.targetReadError,
      affectsTargetExistence: true,
    })
    readFailures.push(failure)
    pushTrace({
      evidenceCode: 'target_read_failed',
      evidenceLabel: '目标业务对象读取失败',
      evidenceCategory: 'target_object',
      targetField: targetNoField || 'targetNo',
      targetValue: targetNo,
      expectedRelation: '目标对象读取成功',
      actualRelation: failure.safeErrorSummary,
      evidenceStatus: 'read_failed',
      failureType: 'target_read_failed',
      failureReason: failure.safeErrorSummary,
      responsibilityCategory: 'read_runtime',
      sourceReadable: false,
    })
  } else if (input.dataFormatError || (rawTarget && !isPlainObject(rawTarget))) {
    const failure = buildReadFailure({
      code: 'target_data_format_failed',
      readStage: 'data_format_parse',
      dataSource: targetObjectType,
      error: input.dataFormatError || '目标对象格式无法解析',
      errorType: 'data_format_error',
      affectsTargetExistence: true,
    })
    readFailures.push(failure)
    pushTrace({
      evidenceCode: 'target_data_format_failed',
      evidenceLabel: '目标业务对象格式校验',
      evidenceCategory: 'read_integrity',
      targetField: targetNoField || 'targetNo',
      targetValue: targetNo,
      expectedRelation: '目标对象结构可解析',
      actualRelation: failure.safeErrorSummary,
      evidenceStatus: 'read_failed',
      failureType: 'data_format_invalid',
      failureReason: failure.safeErrorSummary,
      responsibilityCategory: 'data_format',
      sourceReadable: false,
    })
  } else {
    pushTrace({
      evidenceCode: 'target_object_exists',
      evidenceLabel: '目标业务对象存在性',
      evidenceCategory: 'target_object',
      targetField: targetNoField || 'targetNo',
      targetValue: targetNo,
      expectedRelation: '目标对象存在且编号有效',
      actualRelation: targetExists ? `目标编号 ${targetNo || '空'}` : '未发现目标对象',
      evidenceStatus: targetExists ? 'passed' : 'missing',
      failureType: targetExists ? '' : 'target_not_found',
      failureReason: targetExists ? '' : '未发现目标对象。',
      responsibilityCategory: 'target_business_data',
    })
  }

  const sourceWritebackCompleted = source.flowWritebackStatus === 'written_back'
  const targetSourceLinkCompleted = Boolean(
    target?.sourceLinkStatus === 'linked'
    || (
      target?.sourceObjectType === action.sourceObjectType
      && String(target?.sourceObjectId || '') === String(source?.id || '')
    ),
  )
  const flowLinkCompleted = ['linked', 'active', 'reused'].includes(flowLinkStatus)
    && hasValidIdentifier(linkTargetNo)
    && (!targetNoValid || linkTargetNo === targetNo)
  const transactionStatus = committedAudit?.executionStatus || audits[0]?.executionStatus || ''
  const transactionCommitted = Boolean(committedAudit)
  const statusWritebackCompleted = statusWritebackComplete(input, targetExists)

  const sourceWritebackTrace = pushTrace({
    evidenceCode: 'source_writeback_missing',
    evidenceLabel: '来源对象回写目标编号',
    evidenceCategory: 'source_writeback',
    sourceField: 'flowWritebackStatus',
    sourceValue: source.flowWritebackStatus,
    targetField: targetNoField || 'targetNo',
    targetValue: targetNo,
    expectedRelation: '来源对象已回写目标编号或目标关联信息',
    actualRelation: sourceWritebackCompleted ? '来源已回写' : '来源未回写',
    evidenceStatus: !targetExists ? 'not_applicable' : (sourceWritebackCompleted ? 'passed' : 'missing'),
    failureType: sourceWritebackCompleted || !targetExists ? '' : 'missing_source_writeback',
    failureReason: sourceWritebackCompleted || !targetExists ? '' : '来源对象尚未回写目标编号或目标关联信息。',
    responsibilityCategory: 'relation_writeback',
  })

  const reverseLinkTrace = pushTrace({
    evidenceCode: 'target_source_link_missing',
    evidenceLabel: '目标对象反向关联来源',
    evidenceCategory: 'reverse_link',
    sourceField: 'id',
    sourceValue: source.id || '',
    targetField: 'sourceObjectId',
    targetValue: target.sourceObjectId || '',
    expectedRelation: '目标对象反向指向当前来源对象',
    actualRelation: targetSourceLinkCompleted ? '反向关联一致' : '反向关联缺失或不一致',
    evidenceStatus: !targetExists ? 'not_applicable' : (targetSourceLinkCompleted ? 'passed' : 'missing'),
    failureType: targetSourceLinkCompleted || !targetExists ? '' : 'missing_reverse_link',
    failureReason: targetSourceLinkCompleted || !targetExists ? '' : '目标对象未正确反向指向当前来源对象。',
    responsibilityCategory: 'relation_writeback',
  })

  const processLinkTrace = pushTrace({
    evidenceCode: 'flow_link_missing',
    evidenceLabel: '流程实例关联目标对象',
    evidenceCategory: 'process_link',
    sourceField: 'businessFlowLink.sourceObjectNo',
    sourceValue: sourceNo,
    targetField: 'businessFlowLink.targetObjectNo',
    targetValue: linkTargetNo,
    expectedRelation: '流程关联记录指向当前来源和目标',
    actualRelation: flowLinkCompleted ? '流程关联一致' : '流程关联缺失或目标不一致',
    evidenceStatus: !targetExists ? 'not_applicable' : (flowLinkCompleted ? 'passed' : 'missing'),
    failureType: flowLinkCompleted || !targetExists ? '' : 'missing_process_link',
    failureReason: flowLinkCompleted || !targetExists ? '' : '流程实例关联记录缺失或未指向当前目标。',
    responsibilityCategory: 'process_runtime',
  })

  const transactionTrace = pushTrace({
    evidenceCode: 'transaction_commit_missing',
    evidenceLabel: '事务提交或动作结果证据',
    evidenceCategory: 'transaction_commit',
    sourceField: 'actionAudit.sourceObjectNo',
    sourceValue: sourceNo,
    targetField: 'actionAudit.targetObjectNo',
    targetValue: auditTargetNos,
    expectedRelation: '事务提交证据存在且指向当前目标',
    actualRelation: transactionCommitted ? `事务状态 ${transactionStatus}` : '未发现已提交事务证据',
    evidenceStatus: !targetExists ? 'not_applicable' : (transactionCommitted ? 'passed' : 'missing'),
    failureType: transactionCommitted || !targetExists ? '' : 'missing_transaction_commit',
    failureReason: transactionCommitted || !targetExists ? '' : '未发现已提交的业务动作结果或事务审计证据。',
    responsibilityCategory: 'transaction_evidence',
  })

  const statusWritebackTrace = pushTrace({
    evidenceCode: 'status_writeback_missing',
    evidenceLabel: '状态回写一致性',
    evidenceCategory: 'status_writeback',
    sourceField: 'flowWritebackStatus',
    sourceValue: source.flowWritebackStatus,
    targetField: 'executionStatus',
    targetValue: transactionStatus,
    expectedRelation: '来源状态、目标状态和执行状态互相一致',
    actualRelation: statusWritebackCompleted ? '状态回写未发现异常' : '状态回写证据不完整',
    evidenceStatus: !targetExists ? 'not_applicable' : (statusWritebackCompleted ? 'passed' : 'missing'),
    failureType: statusWritebackCompleted || !targetExists ? '' : 'missing_status_writeback',
    failureReason: statusWritebackCompleted || !targetExists ? '' : '来源状态、目标状态或执行状态回写证据不完整。',
    responsibilityCategory: 'status_writeback',
  })

  const uniquenessTrace = pushTrace({
    evidenceCode: 'multiple_candidate_targets_conflict',
    evidenceLabel: '候选目标唯一性',
    evidenceCategory: 'uniqueness',
    sourceField: 'sourceObjectNo',
    sourceValue: sourceNo,
    targetField: 'candidateTargetNos',
    targetValue: candidateTargets.map((item) => item.targetNo || item.id),
    expectedRelation: '同一来源最多存在一个有效目标对象',
    actualRelation: candidateTargets.length > 1 ? '发现多个候选目标' : '未发现重复候选目标',
    evidenceStatus: candidateTargets.length > 1 ? 'conflict' : (targetExists ? 'passed' : 'not_applicable'),
    failureType: candidateTargets.length > 1 ? 'multiple_target_candidates' : '',
    failureReason: candidateTargets.length > 1 ? '同一来源被识别出多个候选目标，需要人工核对。' : '',
    responsibilityCategory: 'duplicate_target',
  })

  if (input.evidenceReadError) {
    const failure = buildReadFailure({
      code: 'evidence_read_failed',
      readStage: input.evidenceReadStage || 'target_evidence_read',
      dataSource: input.evidenceSourceName || 'flow_link_or_audit',
      error: input.evidenceReadError,
      affectsTargetExistence: false,
    })
    readFailures.push(failure)
  }

  const readIntegrityFailure = readFailures.find((failure) => failure.code === 'evidence_read_failed')
  pushTrace({
    evidenceCode: readIntegrityFailure?.code || 'read_integrity_passed',
    evidenceLabel: readIntegrityFailure ? '关联证据读取失败' : '关联证据读取与解析',
    evidenceCategory: 'read_integrity',
    sourceField: 'runtimeEvidence',
    sourceValue: input.evidenceSourceName || 'business_flow_link_or_audit',
    targetField: 'readStage',
    targetValue: readIntegrityFailure?.readStage || 'all_readable',
    expectedRelation: '目标对象、流程关联和审计证据均可读取并序列化',
    actualRelation: readIntegrityFailure?.safeErrorSummary || '读取与解析成功',
    evidenceStatus: readIntegrityFailure ? 'read_failed' : 'passed',
    failureType: readIntegrityFailure ? 'evidence_read_failed' : '',
    failureReason: readIntegrityFailure?.safeErrorSummary || '',
    responsibilityCategory: readIntegrityFailure ? 'read_runtime' : 'read_runtime',
    sourceReadable: !readIntegrityFailure,
  })

  const missingItems = []
  if (targetExists && !sourceWritebackCompleted) missingItems.push(buildMissingItem('source_writeback_missing', sourceWritebackTrace))
  if (targetExists && !targetSourceLinkCompleted) missingItems.push(buildMissingItem('target_source_link_missing', reverseLinkTrace))
  if (targetExists && !flowLinkCompleted) missingItems.push(buildMissingItem('flow_link_missing', processLinkTrace))
  if (targetExists && !transactionCommitted) missingItems.push(buildMissingItem('transaction_commit_missing', transactionTrace))
  if (targetExists && !statusWritebackCompleted) missingItems.push(buildMissingItem('status_writeback_missing', statusWritebackTrace))
  if (targetExists && cleanupRequired) {
    const cleanupTrace = pushTrace({
      evidenceCode: 'cleanup_required',
      evidenceLabel: '人工清理执行痕迹',
      evidenceCategory: 'transaction_commit',
      sourceField: 'actionAudit.cleanupRequired',
      sourceValue: cleanupRequired,
      targetField: targetNoField || 'targetNo',
      targetValue: targetNo,
      expectedRelation: '无需人工清理',
      actualRelation: '存在需要人工清理的执行痕迹',
      evidenceStatus: 'missing',
      failureType: 'cleanup_required',
      failureReason: '存在需要人工清理的执行痕迹。',
      responsibilityCategory: 'transaction_evidence',
    })
    missingItems.push(buildMissingItem('cleanup_required', cleanupTrace))
  }
  if (targetExists && !targetNoValid) {
    const targetNoTrace = pushTrace({
      evidenceCode: 'target_number_missing',
      evidenceLabel: '目标编号有效性',
      evidenceCategory: 'target_object',
      targetField: targetNoField || 'targetNo',
      targetValue: targetNo,
      expectedRelation: '目标对象编号有效',
      actualRelation: '目标对象存在但编号缺失',
      evidenceStatus: 'missing',
      failureType: 'target_number_missing',
      failureReason: '目标对象存在但没有可确认的目标编号。',
      responsibilityCategory: 'target_business_data',
    })
    missingItems.push(buildMissingItem('target_number_missing', targetNoTrace))
  }

  const conflictItems = []
  if (targetExists && !targetNoValid) {
    conflictItems.push(buildConflictItem({
      code: 'target_number_missing_conflict',
      conflictType: '目标编号缺失',
      rawValue: targetNo,
      compareValue: '目标存在',
      evidenceSource: 'target_object',
      description: '目标对象已存在，但没有可确认的目标编号。',
      traceItem: traceItems.find((item) => item.evidenceCode === 'target_number_missing'),
    }))
  }
  if (targetNoValid && !targetObjectReadable) {
    const traceItem = pushTrace({
      evidenceCode: 'target_no_without_target_conflict',
      evidenceLabel: '目标编号与目标对象存在性',
      evidenceCategory: 'target_object',
      targetField: targetNoField || 'targetNo',
      targetValue: targetNo,
      expectedRelation: '有目标编号时必须能读取目标对象',
      actualRelation: '读取到目标编号但未读取到目标对象',
      evidenceStatus: 'conflict',
      failureType: 'target_number_mismatch',
      failureReason: '运行时读取到目标编号，但未读取到对应目标对象。',
      responsibilityCategory: 'target_business_data',
    })
    conflictItems.push(buildConflictItem({
      code: 'target_no_without_target_conflict',
      conflictType: '编号与对象存在性冲突',
      rawValue: targetNo,
      compareValue: '目标对象不存在',
      evidenceSource: 'runtime_context',
      description: '运行时读取到目标编号，但未读取到对应目标对象。',
      traceItem,
    }))
  }
  if (targetNoValid && hasValidIdentifier(linkTargetNo) && linkTargetNo !== targetNo) {
    processLinkTrace.evidenceStatus = 'conflict'
    processLinkTrace.evidenceStatusLabel = '冲突'
    processLinkTrace.failureType = 'target_number_mismatch'
    processLinkTrace.failureReason = '流程关联记录指向的目标编号与页面识别的目标编号不一致。'
    processLinkTrace.responsibilityCategory = 'process_runtime'
    processLinkTrace.responsibilityLabel = responsibilityLabelMap.process_runtime
    processLinkTrace.blocking = true
    processLinkTrace.actualRelation = `流程目标 ${linkTargetNo}，当前目标 ${targetNo}`
    conflictItems.push(buildConflictItem({
      code: 'flow_link_target_no_conflict',
      conflictType: '流程关联目标编号冲突',
      rawValue: targetNo,
      compareValue: linkTargetNo,
      evidenceSource: 'business_flow_link',
      description: processLinkTrace.failureReason,
      traceItem: processLinkTrace,
    }))
  }
  for (const auditTargetNo of auditTargetNos) {
    if (targetNoValid && auditTargetNo !== targetNo) {
      transactionTrace.evidenceStatus = 'conflict'
      transactionTrace.evidenceStatusLabel = '冲突'
      transactionTrace.failureType = 'target_number_mismatch'
      transactionTrace.failureReason = '事务审计记录指向的目标编号与页面识别的目标编号不一致。'
      transactionTrace.responsibilityCategory = 'transaction_evidence'
      transactionTrace.responsibilityLabel = responsibilityLabelMap.transaction_evidence
      transactionTrace.blocking = true
      transactionTrace.actualRelation = `审计目标 ${auditTargetNo}，当前目标 ${targetNo}`
      conflictItems.push(buildConflictItem({
        code: 'audit_target_no_conflict',
        conflictType: '事务审计目标编号冲突',
        rawValue: targetNo,
        compareValue: auditTargetNo,
        evidenceSource: 'business_flow_audit',
        description: transactionTrace.failureReason,
        traceItem: transactionTrace,
      }))
    }
  }
  if (targetExists && target?.sourceObjectType && target?.sourceObjectType !== action.sourceObjectType) {
    reverseLinkTrace.evidenceStatus = 'conflict'
    reverseLinkTrace.evidenceStatusLabel = '冲突'
    reverseLinkTrace.failureType = 'source_number_mismatch'
    reverseLinkTrace.failureReason = '目标对象记录的来源类型与当前动作来源类型不一致。'
    reverseLinkTrace.responsibilityCategory = 'target_business_data'
    reverseLinkTrace.responsibilityLabel = responsibilityLabelMap.target_business_data
    reverseLinkTrace.blocking = true
    reverseLinkTrace.actualRelation = `目标来源类型 ${target.sourceObjectType}，当前来源类型 ${action.sourceObjectType}`
    conflictItems.push(buildConflictItem({
      code: 'target_reverse_source_type_conflict',
      conflictType: '目标反向来源类型冲突',
      rawValue: target.sourceObjectType,
      compareValue: action.sourceObjectType,
      evidenceSource: 'target_object',
      description: reverseLinkTrace.failureReason,
      traceItem: reverseLinkTrace,
    }))
  }
  if (targetExists && target?.sourceObjectId && source?.id && String(target.sourceObjectId) !== String(source.id)) {
    reverseLinkTrace.evidenceStatus = 'conflict'
    reverseLinkTrace.evidenceStatusLabel = '冲突'
    reverseLinkTrace.failureType = 'source_number_mismatch'
    reverseLinkTrace.failureReason = '目标对象记录的来源 ID 与当前来源 ID 不一致。'
    reverseLinkTrace.responsibilityCategory = 'target_business_data'
    reverseLinkTrace.responsibilityLabel = responsibilityLabelMap.target_business_data
    reverseLinkTrace.blocking = true
    reverseLinkTrace.actualRelation = `目标来源 ${target.sourceObjectId}，当前来源 ${source.id}`
    conflictItems.push(buildConflictItem({
      code: 'target_reverse_source_id_conflict',
      conflictType: '目标反向来源编号冲突',
      rawValue: target.sourceObjectId,
      compareValue: source.id,
      evidenceSource: 'target_object',
      description: reverseLinkTrace.failureReason,
      traceItem: reverseLinkTrace,
    }))
  }
  if (candidateTargets.length > 1) {
    conflictItems.push(buildConflictItem({
      code: 'multiple_candidate_targets_conflict',
      conflictType: '同一来源存在多个候选目标',
      rawValue: candidateTargets.map((item) => item.targetNo || item.id).join('、'),
      compareValue: targetNo || '当前未识别主目标',
      evidenceSource: 'target_store_scan',
      description: uniquenessTrace.failureReason,
      traceItem: uniquenessTrace,
    }))
  }

  const outputStatus = resolveStatusOutput({
    targetExists,
    targetNo,
    readFailures,
    conflictItems,
    missingItems,
  })

  const targetObjectNoDisplay = targetNoValid
    ? targetNo
    : (outputStatus.targetEvidenceStatus === 'read_failed' ? '读取失败' : '尚未生成')
  const abnormalStatuses = new Set(['not_found', 'incomplete', 'conflict', 'read_failed'])
  const nextStepAllowed = !abnormalStatuses.has(outputStatus.targetEvidenceStatus)
  const classificationFailures = []
  if (targetNoValid && targetObjectNoDisplay !== targetNo) classificationFailures.push('target_no_display_not_preserved')
  if (outputStatus.targetEvidenceStatus === 'read_failed' && targetObjectNoDisplay === '尚未生成') classificationFailures.push('read_failed_displayed_as_pending')
  if (outputStatus.targetEvidenceStatus === 'conflict' && conflictItems.length === 0) classificationFailures.push('conflict_without_conflict_items')
  if (outputStatus.targetEvidenceStatus === 'incomplete' && missingItems.length === 0) classificationFailures.push('incomplete_without_missing_items')
  if (outputStatus.targetEvidenceStatus === 'not_found' && readFailures.length > 0) classificationFailures.push('not_found_with_read_failure')

  const firstFailure = firstFailureForStatus(outputStatus.targetEvidenceStatus, traceItems)
  const traceItemsWithFirstFailure = traceItems.map((item) => ({
    ...item,
    firstFailure: item.evidenceCode === firstFailure.targetEvidenceFirstFailureCode
      && item.evidenceCategory === firstFailure.targetEvidenceFirstFailureCategory,
  }))
  const traceCoverage = resolveTraceCoverage(traceItemsWithFirstFailure)
  const sourceConsistency = resolveSourceConsistency({
    traceItems: traceItemsWithFirstFailure,
    missingItems,
    conflictItems,
    readFailures,
  })
  const blockingCount = traceItemsWithFirstFailure.filter((item) => item.blocking).length
  const failedCount = traceItemsWithFirstFailure.filter((item) => ['missing', 'conflict', 'read_failed'].includes(item.evidenceStatus)).length

  return {
    version: BUSINESS_TARGET_EVIDENCE_CLASSIFIER_VERSION,
    inputSnapshot: snapshot,
    targetExists,
    targetNo,
    targetNoValid,
    targetObjectNoRaw: targetNo,
    targetObjectNoDisplay,
    sourceNo,
    linkTargetNo,
    auditTargetNos,
    candidateTargetNos: candidateTargets.map((item) => item.targetNo || item.id).filter(Boolean),
    sourceWritebackCompleted,
    targetSourceLinkCompleted,
    flowLinkStatus,
    flowLinkCompleted,
    transactionStatus,
    transactionCommitted,
    statusWritebackCompleted,
    cleanupRequired,
    duplicateConflict: conflictItems.length > 0,
    targetEvidenceStatus: outputStatus.targetEvidenceStatus,
    targetEvidenceStatusLabel: outputStatus.targetEvidenceStatusLabel,
    targetEvidenceStatusText: outputStatus.targetEvidenceStatusLabel,
    targetEvidenceStatusReason: outputStatus.targetEvidenceStatusReason,
    missingEvidenceCodes: missingItems.map((item) => item.code),
    missingEvidenceTexts: missingItems.map((item) => item.label),
    targetEvidenceMissingItems: missingItems,
    targetEvidenceConflictItems: conflictItems,
    targetEvidenceReadFailures: readFailures,
    targetEvidenceClassificationPassed: classificationFailures.length === 0,
    targetEvidenceClassificationFailures: classificationFailures,
    targetEvidenceTraceItems: traceItemsWithFirstFailure,
    targetEvidenceTracePassedCount: traceItemsWithFirstFailure.filter((item) => item.evidenceStatus === 'passed').length,
    targetEvidenceTraceFailedCount: failedCount,
    targetEvidenceTraceBlockingCount: blockingCount,
    ...traceCoverage,
    ...firstFailure,
    targetEvidenceResponsibilitySummary: summarizeResponsibility(traceItemsWithFirstFailure),
    ...sourceConsistency,
    nextStepAllowed,
    nextStepBlockingReason: nextStepAllowed
      ? '目标证据完整，等待既有业务放行条件判断。'
      : resolveNextStepBlockReason(
        outputStatus.targetEvidenceStatus,
        targetObjectLabel,
        nextStepLabel,
      ),
  }
}

export function getTargetEvidenceStatusLabel(status) {
  return statusLabelMap[status] || String(status || '')
}

export function getTargetEvidenceStatusReason(status) {
  return statusReasonMap[status] || String(status || '')
}

export function getTargetEvidenceResponsibilityLabel(category) {
  return responsibilityLabelMap[category] || String(category || '')
}
