import { emitEvent } from '../orchestration/eventBus.js'

const executionGraph = []

function edgeForStep(previousStep, step) {
  if (!previousStep) return null
  return {
    from: previousStep.module,
    to: step.module,
    action: step.action,
    timestamp: Date.now(),
  }
}

export function runCrossModuleExecution(actionPlan = {}, context = {}) {
  const steps = actionPlan.steps || []
  const edges = steps.map((step, index) => edgeForStep(steps[index - 1], step)).filter(Boolean)
  executionGraph.unshift(...edges)

  const events = steps.map((step, index) => emitEvent({
    type: `${step.module}.${step.action}.executed`,
    source: actionPlan.eventType || context.event?.type || 'execution',
    payload: {
      step,
      actionPlanEvent: actionPlan.eventType,
      executionIndex: index + 1,
      executionEvent: true,
    },
    correlationId: context.event?.correlationId,
    depth: Number(context.event?.depth || 0) + 1,
  }))

  return {
    chain: ['purchase', 'finance', 'inventory', 'scm'],
    edges,
    events,
  }
}

export function getCrossModuleExecutionGraph() {
  return [...executionGraph].slice(0, 40)
}
