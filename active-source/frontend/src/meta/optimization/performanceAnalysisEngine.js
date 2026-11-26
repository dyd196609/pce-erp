export function calculateWorkflowSpeedMetrics(executionData = {}) {
  const performance = executionData.timeline?.performance || {}
  const steps = executionData.timeline?.timeline || []

  return {
    totalDurationMs: performance.totalDurationMs || steps.reduce((total, item) => total + Number(item.durationMs || 0), 0),
    averageStepDurationMs: performance.averageStepDurationMs || (steps.length
      ? Math.round(steps.reduce((total, item) => total + Number(item.durationMs || 0), 0) / steps.length)
      : 0),
    completedSteps: performance.completedSteps || steps.filter((item) => item.status === 'COMPLETED').length,
    blockedSteps: performance.blockedSteps || steps.filter((item) => item.status === 'BLOCKED').length,
  }
}

export function scoreProcessEfficiency(executionData = {}) {
  const metrics = calculateWorkflowSpeedMetrics(executionData)
  const taskConfirmed = (executionData.tasks || []).every((item) => item.confirmation?.confirmed)
  const consistencyBonus = executionData.workflow?.consistency?.consistent ? 12 : 0
  const completionBonus = executionData.completed ? 18 : 0
  const speedPenalty = Math.min(20, Math.round(metrics.averageStepDurationMs / 100))
  const score = Math.max(0, Math.min(100, 70 + consistencyBonus + completionBonus - speedPenalty + (taskConfirmed ? 8 : 0)))

  return {
    score,
    grade: score >= 90 ? 'A' : score >= 80 ? 'B' : 'C',
    metrics,
  }
}

export function analyzeDepartmentPerformance(executionData = {}) {
  const tasks = executionData.tasks || []
  const byRole = tasks.reduce((acc, item) => {
    const role = item.assigned?.role || 'Process Owner'
    if (!acc[role]) {
      acc[role] = {
        role,
        completed: 0,
        total: 0,
      }
    }
    acc[role].total += 1
    if (item.validation?.valid) acc[role].completed += 1
    return acc
  }, {})

  return Object.values(byRole).map((item) => ({
    ...item,
    completionRate: item.total ? item.completed / item.total : 0,
    performance: item.completed === item.total ? 'GOOD' : 'REVIEW',
  }))
}

export function analyzePerformance(executionData = {}) {
  return {
    processEfficiency: scoreProcessEfficiency(executionData),
    departmentPerformance: analyzeDepartmentPerformance(executionData),
    workflowSpeed: calculateWorkflowSpeedMetrics(executionData),
  }
}
