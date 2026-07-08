export function predictProcessDuration(context = {}) {
  const executionData = context.executionClosedLoop || context.executionData || context
  const timeline = executionData.timeline?.timeline || []
  const measuredDuration = timeline.reduce((sum, item) => sum + (item.durationMs || 0), 0)
  const fallbackDuration = Math.max(1, executionData.tasks?.length || 3) * 1200

  return {
    processDurationPrediction: 'ACTIVE',
    durationMs: measuredDuration || fallbackDuration,
    basis: measuredDuration ? 'TIMELINE_HISTORY' : 'TASK_COUNT_ESTIMATE',
  }
}

export function predictApprovalDelay(context = {}) {
  const approvalProbability = context.approvalProbability?.probability || 0.75
  const delayMs = Math.round((1 - approvalProbability) * 4800)

  return {
    approvalDelayPrediction: 'ACTIVE',
    delayMs,
    delayRisk: delayMs > 1800 ? 'REVIEW_DELAY_POSSIBLE' : 'NORMAL_APPROVAL_WINDOW',
  }
}

export function predictTime(context = {}) {
  const processDuration = predictProcessDuration(context)
  const approvalDelay = predictApprovalDelay(context)
  const executionTimeMs = processDuration.durationMs + approvalDelay.delayMs

  return {
    timePrediction: 'ACTIVE',
    processDuration,
    approvalDelay,
    executionTimeMs,
    etaLabel: `${Math.ceil(executionTimeMs / 1000)}s predicted execution window`,
  }
}
