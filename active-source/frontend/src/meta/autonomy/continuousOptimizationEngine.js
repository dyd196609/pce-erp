import { optimizeWorkflow } from '../governance/workflowOptimizationAI.js'

export function tuneSystem(context = {}) {
  const feedback = context.feedback || {}
  const latency = Number(feedback.latency || 180)
  const backlog = Number(feedback.workflowBacklog || 4)

  return {
    mode: 'V30_SYSTEM_SELF_TUNING',
    parameters: {
      decisionThreshold: backlog > 5 ? 0.72 : 0.78,
      batchWindowMinutes: latency > 250 ? 5 : 2,
      financeReserveRatio: Number(feedback.cashPressure || 0) > 0.4 ? 0.22 : 0.15,
    },
    tuningAction: backlog > 5 ? 'INCREASE_AUTOPILOT_THROUGHPUT' : 'MAINTAIN_BALANCED_RUNTIME',
  }
}

export function optimizePerformance(context = {}) {
  const feedback = context.feedback || {}
  const baseline = Number(feedback.performanceScore || 82)
  const optimizedScore = Math.min(100, baseline + 8)

  return {
    mode: 'V30_PERFORMANCE_OPTIMIZATION',
    baseline,
    optimizedScore,
    improvement: optimizedScore - baseline,
    actions: ['rebalance_workflow_queue', 'compress_decision_path', 'pre_schedule_financial_ops'],
  }
}

export function restructureWorkflow(context = {}) {
  const workflowOptimization = optimizeWorkflow(context)

  return {
    mode: 'V30_WORKFLOW_RESTRUCTURING',
    workflowOptimization,
    restructureAction: workflowOptimization.approvals.removed > 0
      ? 'REMOVE_REDUNDANT_APPROVALS'
      : workflowOptimization.path.priority === 'HIGH'
        ? 'FAST_TRACK_CRITICAL_PATH'
        : 'KEEP_STABLE_PATH',
    expectedCycleTimeReduction: workflowOptimization.path.expectedCycleTimeReduction,
  }
}

export function continuousOptimization(context = {}) {
  const selfTuning = tuneSystem(context)
  const performance = optimizePerformance(context)
  const workflow = restructureWorkflow(context)
  const selfOptimizationRate = Math.min(1, (
    performance.improvement / 20
    + workflow.expectedCycleTimeReduction
    + (selfTuning.tuningAction === 'INCREASE_AUTOPILOT_THROUGHPUT' ? 0.2 : 0.1)
  ) / 1.2)

  return {
    mode: 'V30_CONTINUOUS_OPTIMIZATION_ENGINE',
    continuousOptimization: 'ENABLED',
    selfTuning,
    performance,
    workflow,
    metrics: {
      systemSelfOptimizationRate: selfOptimizationRate,
      performanceOptimizationScore: performance.optimizedScore,
      workflowRestructuringImpact: workflow.expectedCycleTimeReduction,
    },
  }
}
