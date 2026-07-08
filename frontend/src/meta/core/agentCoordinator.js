import { resolveAgentConflicts } from './agentConflictResolver.js'
import { registerAgent } from './agentRegistry.js'
import { financeAgent } from './financeAgent.js'
import { inventoryAgent } from './inventoryAgent.js'
import { procurementAgent } from './procurementAgent.js'
import { distributeTask } from './taskDistributor.js'

registerAgent('PROCUREMENT', procurementAgent)
registerAgent('INVENTORY', inventoryAgent)
registerAgent('FINANCE', financeAgent)

export function coordinateAgents(plan, decisions = []) {
  const results = []

  plan.tasks.forEach((task, index) => {
    const decision = decisions[index]

    if (decision?.finalDecision?.decision === 'BLOCK' || decision?.finalDecision?.decision === 'RESTRICT') {
      results.push({
        agent: 'NONE',
        task,
        status: 'BLOCKED',
        result: `Blocked task: ${task.step}`,
        decision,
      })
      return
    }

    results.push({
      task,
      status: decision?.finalDecision?.decision === 'MONITOR' ? 'REVIEW_MODE' : 'EXECUTED',
      decision,
      ...distributeTask(task),
    })
  })

  return {
    mode: 'MULTI_AGENT_EXECUTION',
    results,
    conflicts: resolveAgentConflicts(results),
  }
}
