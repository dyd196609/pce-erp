import { evaluateDecision, getIntelligenceSnapshot } from '../intelligence/decisionEngine.js'
import { executeActionPlan, getExecutionLayerSnapshot } from '../execution/executionEngine.js'
import { runContinuousExecution, getContinuousExecutionSnapshot } from './continuousExecutionEngine.js'
import { autoRepair, getSelfRepairSnapshot } from './selfRepairEngine.js'
import { runFinancialAutonomy, getFinancialAutonomySnapshot } from './financialAutonomyEngine.js'
import { runGoalBasedExecution } from './zeroHumanLayer.js'

const autopilotHistory = []

export function autoDecide(context = {}) {
  if (context.decision) return context.decision
  if (context.event) return evaluateDecision(context.event)

  const latest = getIntelligenceSnapshot().latest
  return latest || evaluateDecision({
    id: `autopilot-decision-${Date.now()}`,
    type: 'autopilot.heartbeat',
    payload: {
      goal: context.goal || 'enterprise_continuity',
    },
  })
}

export function autoExecute(context = {}) {
  const decision = context.decision || autoDecide(context)
  const zeroHuman = runGoalBasedExecution({
    ...context,
    decision,
    risk: decision.risk,
  })

  if (!zeroHuman.allowed) {
    return {
      status: 'WAITING_FOR_REPAIR',
      zeroHuman,
    }
  }

  return executeActionPlan(decision.actionPlan, {
    ...context,
    decision: decision.decision,
    risk: decision.risk,
  })
}

export function continuousOptimize(context = {}) {
  const execution = context.executionSnapshot || getExecutionLayerSnapshot()
  const stability = execution.history.some((item) => item.status === 'BLOCKED') ? 'CONTROLLED' : 'STABLE'

  return {
    status: 'OPTIMIZED',
    stability,
    recommendation: stability === 'STABLE' ? 'KEEP_AUTOPILOT_RUNNING' : 'RUN_SELF_REPAIR',
    timestamp: Date.now(),
  }
}

export function runEnterpriseAutopilot(context = {}) {
  const decisions = autoDecide(context)
  const continuous = runContinuousExecution(context)
  const execution = autoExecute({
    ...context,
    decision: decisions,
  })
  const repair = autoRepair({
    ...context,
    executionSnapshot: getExecutionLayerSnapshot(),
  })
  const finance = runFinancialAutonomy({
    financialRecords: getExecutionLayerSnapshot().financialRecords,
  })
  const optimization = continuousOptimize({
    ...context,
    executionSnapshot: getExecutionLayerSnapshot(),
  })

  const result = {
    autopilotMode: 'ON',
    zeroHumanOperation: 'ACTIVE',
    continuousExecution: 'ENABLED',
    selfRepair: 'ACTIVE',
    decisions,
    execution,
    repair,
    financialAutonomy: finance,
    continuous,
    optimization,
    timestamp: Date.now(),
  }

  autopilotHistory.unshift(result)
  if (autopilotHistory.length > 80) autopilotHistory.length = 80

  return result
}

export function getEnterpriseAutopilotSnapshot() {
  const continuous = getContinuousExecutionSnapshot()
  const repair = getSelfRepairSnapshot()
  const finance = getFinancialAutonomySnapshot()
  const execution = getExecutionLayerSnapshot()
  const total = autopilotHistory.length || 1
  const stable = autopilotHistory.filter((item) => item.optimization?.stability === 'STABLE').length

  return {
    autopilotMode: 'ON',
    zeroHumanOperation: 'ACTIVE',
    continuousExecution: 'ENABLED',
    selfRepair: 'ACTIVE',
    latest: autopilotHistory[0] || null,
    history: [...autopilotHistory],
    continuous,
    repair,
    finance,
    execution,
    metrics: {
      autopilotStabilityIndex: autopilotHistory.length ? Math.round((stable / total) * 100) : 100,
      continuousExecutionRate: continuous.metrics.continuousExecutionRate,
      selfRepairSuccessRate: repair.metrics.selfRepairSuccessRate,
      financialAutonomyScore: finance.metrics.financialAutonomyScore,
    },
  }
}
