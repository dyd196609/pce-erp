import { recordEvent } from './monitoringLayer.js'
import { runUnifiedDecisionKernel } from './unifiedDecisionKernel.js'

export function decideTasks(plan) {
  return plan.tasks.map((task) =>
    runUnifiedDecisionKernel({
      task,
      goal: plan.goal,
      type: plan.type,
    })
  )
}

export async function executeTasks(plan) {
  const decisions = decideTasks(plan)
  const results = decisions.map((decision, index) => {
    const task = plan.tasks[index]
    const final = decision.finalDecision?.decision
    const status = final === 'BLOCK' || final === 'RESTRICT'
      ? 'BLOCKED'
      : final === 'MONITOR'
        ? 'REVIEW_MODE'
        : 'EXECUTED'

    recordEvent({
      type: 'AGENT_TASK',
      module: 'agent',
      status,
      step: task.step,
    })

    return {
      task,
      status,
      decision,
    }
  })

  return {
    plan,
    decisions,
    results,
  }
}
