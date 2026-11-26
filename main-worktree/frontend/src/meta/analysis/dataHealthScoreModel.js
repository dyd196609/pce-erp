const DEFAULT_OPERATION_CAPABILITY = {
  sorting: true,
  exportCurrentResult: true,
  advancedFilter: true,
  diagnosticCopy: true,
}

export const ENTERPRISE_DATA_HEALTH_SCORE_VERSION = 'V1.13.31'

export function buildEnterpriseDataHealthScore({
  trace = null,
  businessTraceAnalysis = null,
  amountReconciliation = null,
  operationCapability = DEFAULT_OPERATION_CAPABILITY,
} = {}) {
  const chainScore = scoreByPercent(businessTraceAnalysis?.chainCompleteness?.percent, 30)
  const amountScore = scoreAmountConsistency(amountReconciliation || businessTraceAnalysis?.amountConsistency)
  const evidenceScore = scoreByPercent(businessTraceAnalysis?.evidenceCompleteness?.percent, 20)
  const riskClosureScore = scoreRiskClosure(trace)
  const operationScore = scoreOperationConsistency(operationCapability)
  const dimensionScores = [
    {
      key: 'chainCompleteness',
      name: '业务链完整度',
      weight: 30,
      score: chainScore,
      source: 'businessTraceAnalysis.chainCompleteness',
      summary: businessTraceAnalysis?.chainCompleteness?.summary || '业务链完整度待确认。',
    },
    {
      key: 'amountConsistency',
      name: '金额一致性',
      weight: 25,
      score: amountScore,
      source: 'amountReconciliation',
      summary: amountReconciliation?.amountConclusion || businessTraceAnalysis?.amountConsistency?.amountConclusion || '金额一致性待确认。',
    },
    {
      key: 'evidenceCompleteness',
      name: '证据完整度',
      weight: 20,
      score: evidenceScore,
      source: 'businessTraceAnalysis.evidenceCompleteness',
      summary: businessTraceAnalysis?.evidenceCompleteness?.summary || '证据完整度待确认。',
    },
    {
      key: 'riskClosureStatus',
      name: '风险闭环状态',
      weight: 15,
      score: riskClosureScore,
      source: 'P2P验证与闭环中心风险生命周期',
      summary: riskClosureSummary(trace),
    },
    {
      key: 'operationConsistency',
      name: '操作一致性',
      weight: 10,
      score: operationScore,
      source: '列表基础能力',
      summary: operationConsistencySummary(operationCapability),
    },
  ]
  const overallScore = clampScore(dimensionScores.reduce((sum, item) => sum + item.score, 0))
  const deductionReasons = buildDeductionReasons({
    trace,
    businessTraceAnalysis,
    amountReconciliation,
    operationCapability,
  })
  const scoreLevel = resolveScoreLevel(overallScore, amountReconciliation || businessTraceAnalysis?.amountConsistency)
  return {
    version: ENTERPRISE_DATA_HEALTH_SCORE_VERSION,
    overallScore,
    scoreLevel,
    dimensionScores,
    deductionReasons,
    scoreConclusion: buildScoreConclusion({ overallScore, scoreLevel, deductionReasons }),
    isOfficialKpi: false,
    writeBusinessData: false,
  }
}

function scoreByPercent(percent = 0, weight = 0) {
  const safePercent = Number.isFinite(Number(percent)) ? Number(percent) : 0
  return clampScore(Math.round((Math.max(0, Math.min(100, safePercent)) / 100) * weight))
}

function scoreAmountConsistency(amount = {}) {
  if (amount?.amountStatus === 'matched') return 25
  if (amount?.amountStatus === 'difference') return 15
  return 18
}

function scoreRiskClosure(trace = {}) {
  if (!trace) return 12
  if (trace.riskStatus === 'normal') return 15
  if (trace.riskStatus === 'amount_check') return 15
  if (trace.riskStatus === 'attention') return 10
  return 8
}

function scoreOperationConsistency(operationCapability = {}) {
  const checks = ['sorting', 'exportCurrentResult', 'advancedFilter', 'diagnosticCopy']
  const completed = checks.filter((key) => operationCapability?.[key]).length
  return clampScore(Math.round((completed / checks.length) * 10))
}

function buildDeductionReasons({
  trace = null,
  businessTraceAnalysis = null,
  amountReconciliation = null,
  operationCapability = {},
} = {}) {
  const reasons = []
  const missingNodes = businessTraceAnalysis?.chainCompleteness?.missingNodeCount || 0
  if (missingNodes > 0) {
    reasons.push(businessTraceAnalysis.chainCompleteness.summary)
  }
  const amount = amountReconciliation || businessTraceAnalysis?.amountConsistency || {}
  if (amount.amountStatus === 'difference') {
    reasons.push(amount.amountConclusion || '采购金额、应付金额或付款金额存在差异，需要业务核对。')
  } else if (amount.amountStatus === 'pending') {
    reasons.push('金额依据尚未完全确认，需等待最终应付或付款对象。')
  }
  const missingEvidence = businessTraceAnalysis?.evidenceCompleteness?.missingEvidenceCount || 0
  if (missingEvidence > 0) {
    reasons.push(businessTraceAnalysis.evidenceCompleteness.summary)
  }
  if (trace?.riskStatus && !['normal', 'amount_check'].includes(trace.riskStatus)) {
    reasons.push(trace.riskStatusText || '当前业务链存在需关注事项。')
  }
  const missingOperations = operationMissingLabels(operationCapability)
  if (missingOperations.length) {
    reasons.push(`列表基础能力待补齐：${missingOperations.join('、')}。`)
  }
  return reasons.length ? reasons : ['暂无扣分项。']
}

function riskClosureSummary(trace = {}) {
  if (!trace) return '未选择业务链，风险闭环状态待确认。'
  if (trace.riskStatus === 'normal') return '当前业务链未发现未闭环风险。'
  if (trace.riskStatus === 'amount_check') return '当前仅存在金额待核对提示，不按未闭环严重风险重复扣分。'
  return trace.riskStatusText || '当前业务链存在需关注事项，需在 P2P验证与闭环中心确认。'
}

function operationConsistencySummary(operationCapability = {}) {
  const missing = operationMissingLabels(operationCapability)
  if (!missing.length) return '排序、导出、高级筛选和复制诊断能力已具备。'
  return `仍需补齐：${missing.join('、')}。`
}

function operationMissingLabels(operationCapability = {}) {
  const labels = {
    sorting: '排序',
    exportCurrentResult: '导出当前结果',
    advancedFilter: '高级筛选',
    diagnosticCopy: '复制诊断数据',
  }
  return Object.entries(labels)
    .filter(([key]) => !operationCapability?.[key])
    .map(([, label]) => label)
}

function resolveScoreLevel(score, amount = {}) {
  if (score >= 90) {
    return amount?.amountStatus === 'difference' ? '健康，但金额需要核对' : '健康'
  }
  if (score >= 70) return '需关注'
  if (score >= 50) return '存在风险'
  return '严重风险'
}

function buildScoreConclusion({ overallScore = 0, scoreLevel = '', deductionReasons = [] } = {}) {
  if (deductionReasons.length && deductionReasons[0] !== '暂无扣分项。') {
    return `综合健康评分 ${overallScore} / 100，等级为${scoreLevel}；主要关注：${deductionReasons.join('；')}`
  }
  return `综合健康评分 ${overallScore} / 100，等级为${scoreLevel}；当前业务链数据健康。`
}

function clampScore(value) {
  const number = Number(value || 0)
  if (!Number.isFinite(number)) return 0
  return Math.max(0, Math.min(100, number))
}
