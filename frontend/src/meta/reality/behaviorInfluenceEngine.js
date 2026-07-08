function resolveFeedback(context = {}) {
  return context.feedback || context.realWorldFeedback || {}
}

export function influenceApprovalSpeed(context = {}) {
  const feedback = resolveFeedback(context)
  const delayRate = Number(feedback.approvalDelayRate ?? 0.18)
  const urgency = feedback.urgent === true || delayRate > 0.3

  return {
    target: 'approval_speed',
    currentDelayRate: delayRate,
    influence: urgency ? 'ACCELERATE_APPROVAL' : 'MAINTAIN_APPROVAL_RHYTHM',
    expectedChange: urgency ? -0.12 : -0.03,
  }
}

export function influenceWorkflowPriority(context = {}) {
  const feedback = resolveFeedback(context)
  const backlog = Number(feedback.workflowBacklog ?? 6)

  return {
    target: 'workflow_priority',
    backlog,
    priority: backlog > 10 ? 'HIGH' : backlog > 3 ? 'MEDIUM' : 'NORMAL',
    influence: backlog > 10 ? 'PROMOTE_BOTTLENECK_WORKFLOWS' : 'KEEP_STANDARD_QUEUE',
  }
}

export function influenceExecutionOrder(context = {}) {
  const feedback = resolveFeedback(context)
  const risk = Number(feedback.executionRisk ?? 0.2)
  const cashPressure = Number(feedback.cashPressure ?? 0.25)

  return {
    target: 'execution_order',
    order: cashPressure > 0.5
      ? ['cash_sensitive_workflows', 'customer_orders', 'internal_tasks']
      : risk > 0.5
      ? ['low_risk_tasks', 'manual_review_tasks', 'high_risk_tasks']
      : ['customer_orders', 'supply_chain_tasks', 'internal_tasks'],
    influence: cashPressure > 0.5 ? 'CASHFLOW_FIRST' : risk > 0.5 ? 'RISK_REDUCTION_FIRST' : 'VALUE_FIRST',
  }
}

export function influenceRealityBehavior(context = {}) {
  return {
    mode: 'V28_REALITY_BEHAVIOR_INFLUENCE',
    approvalSpeed: influenceApprovalSpeed(context),
    workflowPriority: influenceWorkflowPriority(context),
    executionOrder: influenceExecutionOrder(context),
  }
}
