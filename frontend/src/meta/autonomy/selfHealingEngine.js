import {
  autoFixBrokenTransitions,
  detectWorkflowFailure,
  getSelfRepairSnapshot,
  restoreSystemConsistency,
} from './selfRepairEngine.js'

const healingHistory = []

export function detectFailures(context = {}) {
  return detectWorkflowFailure(context)
}

export function detectFailure(context = {}) {
  const failure = detectFailures(context)
  const execution = context.executionClosedLoop || context.execution || {}
  const autonomousExecution = context.autonomousExecution || {}
  const hasBreakpoints = (execution.breakpoints || []).length > 0
  const executionBlocked = autonomousExecution.executed === false
    && autonomousExecution.executionMode === 'CONTROLLED_AUTONOMY'

  return {
    ...failure,
    failureDetected: failure.failed === true || hasBreakpoints || executionBlocked,
    breakpoints: execution.breakpoints || [],
    autonomousExecutionState: autonomousExecution.executionMode || 'UNKNOWN',
  }
}

export function autoRepairWorkflows(failure = {}) {
  return autoFixBrokenTransitions(failure)
}

export function rollbackTransaction(failure = {}) {
  return {
    rollbackTransaction: failure.failureDetected ? 'ROLLBACK_APPLIED' : 'NOT_REQUIRED',
    transactionSafe: true,
    reason: failure.failureDetected ? 'Failure detected before autonomous commit' : 'No failure detected',
  }
}

export function restoreConsistency(repair = {}) {
  return restoreSystemConsistency(repair)
}

export function repairWorkflowState(context = {}) {
  const failure = context.failure || detectFailure(context)
  const rollback = rollbackTransaction(failure)
  const repair = autoRepairWorkflows(failure)
  const consistency = restoreConsistency(repair)

  return {
    repairWorkflowState: 'ACTIVE',
    failure,
    rollback,
    repair,
    consistency,
  }
}

export function autoRepair(context = {}) {
  const repairedState = repairWorkflowState(context)

  return {
    selfHealing: 'ACTIVE',
    detectFailure: repairedState.failure,
    rollback: repairedState.rollback,
    workflowState: repairedState,
    consistency: repairedState.consistency,
  }
}

export function selfHeal(context = {}) {
  const failures = detectFailure(context)
  const repair = autoRepairWorkflows(failures)
  const consistency = restoreConsistency(repair)
  const result = {
    mode: 'V30_SELF_HEALING_ENGINE',
    selfHealing: 'ACTIVE',
    failures,
    repair,
    consistency,
    timestamp: Date.now(),
  }

  healingHistory.unshift(result)
  if (healingHistory.length > 100) healingHistory.length = 100

  return result
}

export function getSelfHealingSnapshot() {
  return {
    selfHealing: 'ACTIVE',
    latest: healingHistory[0] || null,
    history: [...healingHistory],
    repair: getSelfRepairSnapshot(),
    metrics: {
      healedIncidents: healingHistory.filter((item) => item.consistency?.consistent).length,
      selfHealingRate: healingHistory.length
        ? Math.round((healingHistory.filter((item) => item.consistency?.consistent).length / healingHistory.length) * 100)
        : 100,
    },
  }
}
