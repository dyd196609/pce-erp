export function validateRisk(actionPlan = {}, context = {}) {
  const risk = context.risk || actionPlan.risk || {}
  const score = Number(risk.score || 0)
  const level = risk.level || 'LOW'
  const executable = actionPlan.executable !== false

  if (!executable) {
    return {
      safe: false,
      status: 'BLOCKED',
      reason: 'action_plan_not_executable',
      risk,
    }
  }

  if (score >= 90 || level === 'CRITICAL') {
    return {
      safe: false,
      status: 'BLOCKED',
      reason: 'risk_above_execution_threshold',
      risk,
    }
  }

  return {
    safe: true,
    status: level === 'HIGH' ? 'CONTROLLED' : 'ALLOWED',
    reason: level === 'HIGH' ? 'high_risk_controlled_execution' : 'risk_within_auto_execution_limit',
    risk,
  }
}

export function shouldAutoExecute(actionPlan = {}, context = {}) {
  return validateRisk(actionPlan, context).safe
}
