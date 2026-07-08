const transitionByAction = {
  triggerReorder: 'submitted',
  createOrder: 'submitted',
  reviewPayable: 'reviewed',
  validateSupplierCost: 'approved',
  confirmDeliverySchedule: 'in_transit',
  requestApprovalReview: 'review',
  monitorEventChain: 'monitoring',
  trackEvent: 'monitoring',
}

export function autoStateTransition(step = {}, context = {}) {
  return {
    module: step.module,
    action: step.action,
    from: context.currentState || 'auto',
    to: transitionByAction[step.action] || 'completed',
    status: 'TRANSITIONED',
    timestamp: Date.now(),
  }
}

export function autoApprovalProgression(step = {}, context = {}) {
  const controlled = context.risk?.level === 'HIGH'

  return {
    module: step.module,
    action: step.action,
    approvalStatus: controlled ? 'CONTROLLED_APPROVAL' : 'AUTO_APPROVED',
    approver: controlled ? 'riskGate' : 'workflowAutopilot',
    timestamp: Date.now(),
  }
}

export function autoWorkflowCompletion(steps = [], context = {}) {
  return {
    status: steps.length ? 'COMPLETED' : 'NO_ACTION',
    completedSteps: steps.length,
    controlled: context.risk?.level === 'HIGH',
    timestamp: Date.now(),
  }
}

export function runWorkflowAutopilot(actionPlan = {}, context = {}) {
  const steps = actionPlan.steps || []

  return {
    transitions: steps.map((step) => autoStateTransition(step, context)),
    approvals: steps.map((step) => autoApprovalProgression(step, context)),
    completion: autoWorkflowCompletion(steps, context),
  }
}
