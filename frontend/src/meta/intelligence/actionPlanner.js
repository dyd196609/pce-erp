const moduleActions = {
  cost_optimization: [
    { module: 'finance', action: 'reviewPayable' },
    { module: 'purchase', action: 'validateSupplierCost' },
  ],
  supply_chain_optimization: [
    { module: 'purchase', action: 'triggerReorder' },
    { module: 'scm', action: 'confirmDeliverySchedule' },
  ],
  revenue_optimization: [
    { module: 'crm', action: 'confirmDeal' },
    { module: 'purchase', action: 'createOrder' },
  ],
  risk_mitigation: [
    { module: 'workflow', action: 'requestApprovalReview' },
    { module: 'ops', action: 'monitorEventChain' },
  ],
  operational_monitoring: [
    { module: 'ops', action: 'trackEvent' },
  ],
}

export function convertDecisionToSteps(decision = {}, strategy = {}, risk = {}) {
  const primary = strategy.primary?.type || 'operational_monitoring'
  const sourceSteps = moduleActions[primary] || moduleActions.operational_monitoring

  return sourceSteps.map((step, index) => ({
    id: `${primary}-${index + 1}`,
    module: step.module,
    action: step.action,
    status: decision.action === 'BLOCK_AUTOMATION' ? 'PENDING_REVIEW' : 'READY',
    schedule: risk.level === 'HIGH' ? 'IMMEDIATE' : index === 0 ? 'NOW' : 'NEXT',
  }))
}

export function assignModuleResponsibility(steps = []) {
  return steps.reduce((map, step) => ({
    ...map,
    [step.module]: [...(map[step.module] || []), step.action],
  }), {})
}

export function scheduleWorkflowExecution(steps = [], risk = {}) {
  return steps.map((step, index) => ({
    ...step,
    order: index + 1,
    executionWindow: step.schedule === 'IMMEDIATE' || risk.level === 'HIGH' ? 'T+0' : `T+${index}`,
  }))
}

export function createActionPlan(event = {}, decision = {}, strategy = {}, risk = {}) {
  const steps = convertDecisionToSteps(decision, strategy, risk)

  return {
    executable: decision.action !== 'BLOCK_AUTOMATION',
    eventType: event.type || 'unknown.event',
    steps: scheduleWorkflowExecution(steps, risk),
    responsibility: assignModuleResponsibility(steps),
    createdAt: Date.now(),
  }
}
