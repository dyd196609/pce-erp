const activationEvents = []

export const activationSteps = {
  FIRST_LOGIN: 'first login',
  FIRST_WORKFLOW_EXECUTION: 'first workflow execution',
  FIRST_MODULE_USAGE: 'first module usage',
  FIRST_AI_DECISION: 'first AI decision',
}

function normalizeStep(step) {
  return activationSteps[step] || step || activationSteps.FIRST_MODULE_USAGE
}

export function recordActivation(event = {}) {
  const entry = {
    tenantId: event.tenantId || event.tenant?.id || 'demo_company',
    step: normalizeStep(event.step),
    module: event.module || 'dashboard',
    timestamp: Date.now(),
  }

  activationEvents.push(entry)
  return entry
}

export function getActivationEvents(tenantId) {
  return activationEvents.filter((event) => !tenantId || event.tenantId === tenantId)
}

export function getActivationFunnel(tenantId) {
  const events = getActivationEvents(tenantId)
  const completed = new Set(events.map((event) => event.step))
  const steps = Object.values(activationSteps).map((step) => ({
    step,
    completed: completed.has(step),
  }))

  return {
    tenantId: tenantId || 'ALL',
    steps,
    completed: steps.filter((step) => step.completed).length,
    total: steps.length,
    activationRate: steps.length === 0 ? 0 : steps.filter((step) => step.completed).length / steps.length,
    activationScore: steps.length === 0 ? 0 : Math.round((steps.filter((step) => step.completed).length / steps.length) * 100),
  }
}

export function calculateActivationScore(tenantId) {
  return getActivationFunnel(tenantId).activationScore
}

export function clearActivationEvents() {
  activationEvents.length = 0
}
