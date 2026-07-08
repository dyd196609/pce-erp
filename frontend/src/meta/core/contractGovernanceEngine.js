import { enforceContractRules } from './contractEnforcementEngine.js'
import { suggestRepair } from './contractRepairEngine.js'
import { triggerAutoHealingIfMonitor } from './monitoringLayer.js'

export function runContractGovernance() {
  const enforcement = enforceContractRules()
  const repair = suggestRepair()

  let decision = 'ALLOW'

  if (enforcement.status.level === 'WARNING') {
    decision = 'MONITOR'
  }

  if (enforcement.status.level === 'CRITICAL') {
    decision = 'RESTRICT'
  }

  if (enforcement.status.level === 'BLOCK') {
    decision = 'BLOCK_SYSTEM'
  }

  const result = {
    drift: enforcement.drift,
    status: enforcement.status,
    suggestions: repair,
    decision,
  }

  triggerAutoHealingIfMonitor(result, {
    source: 'contractGovernance',
  })

  return result
}
