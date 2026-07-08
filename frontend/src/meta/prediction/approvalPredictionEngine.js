function clampScore(score) {
  return Math.max(0.05, Math.min(0.98, score))
}

export function calculateApproval(context = {}) {
  const executionData = context.executionClosedLoop || context.executionData || context
  const consistent = executionData.workflow?.consistency?.consistent !== false
  const completedTasks = (executionData.tasks || []).filter((task) => task.status === 'completed').length
  const taskCount = Math.max(1, executionData.tasks?.length || 1)
  const blockedCount = executionData.breakpoints?.length || 0
  const bottleneckCount = context.optimizationRuntime?.process?.bottlenecks?.length
    || context.processOptimization?.bottlenecks?.length
    || 0

  const base = 0.72
  const taskSignal = (completedTasks / taskCount) * 0.16
  const consistencySignal = consistent ? 0.08 : -0.18
  const riskPenalty = blockedCount * 0.12 + bottleneckCount * 0.04
  const probability = clampScore(base + taskSignal + consistencySignal - riskPenalty)

  return {
    approvalPrediction: 'ACTIVE',
    probability,
    probabilityScore: Math.round(probability * 100),
    forecast: probability >= 0.8 ? 'LIKELY_APPROVED' : probability >= 0.6 ? 'NEEDS_REVIEW' : 'HIGH_REJECTION_RISK',
    factors: {
      workflowConsistency: consistent,
      taskCompletionRate: completedTasks / taskCount,
      blockedCount,
      bottleneckCount,
    },
  }
}

export function predictApproval(context = {}) {
  return calculateApproval(context)
}
