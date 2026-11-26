import { getAgent } from './agentRegistry.js'

export function distributeTask(task) {
  if (task.step.includes('purchase')) {
    return getAgent('PROCUREMENT')(task)
  }

  if (task.step.includes('stock')) {
    return getAgent('INVENTORY')(task)
  }

  if (task.step.includes('finance')) {
    return getAgent('FINANCE')(task)
  }

  return {
    agent: 'GENERAL',
    result: `Unhandled task: ${task.step}`,
  }
}
